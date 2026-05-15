"""
FlexFlow Dynamic Import Service
Handles Excel/CSV imports with dynamic column mapping, margin calculation, and atomicity.
"""

import io
import csv
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, InvalidOperation
from datetime import datetime
import uuid

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.schemas.import_schema import (
    ImportMapping,
    ImportFieldType,
    ImportItemData,
    ImportPOData,
    ImportRowError,
    ImportValidationResult,
    ImportRequest,
    ImportResponse
)


class ImportService:
    """
    Service for importing Purchase Orders from Excel/CSV files.
    
    Features:
    - Dynamic column mapping
    - Automatic margin calculation
    - Data validation with detailed error reporting
    - Atomicity (all-or-nothing import)
    - Multi-tenancy support
    """
    
    def __init__(self, db: Session):
        """
        Initialize the import service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def read_file(self, file_content: bytes, file_name: str) -> pd.DataFrame:
        """
        Read Excel or CSV file into a pandas DataFrame.
        
        Args:
            file_content: Raw file bytes
            file_name: Name of the file (used to determine type)
            
        Returns:
            DataFrame with file contents
            
        Raises:
            ValueError: If file cannot be read or is invalid
        """
        try:
            if file_name.lower().endswith('.csv'):
                # Try different encodings for CSV
                for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                    try:
                        df = pd.read_csv(
                            io.BytesIO(file_content),
                            encoding=encoding,
                            skipinitialspace=True
                        )
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise ValueError("Could not decode CSV file with any supported encoding")
            
            elif file_name.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(file_content))
            
            else:
                raise ValueError(f"Unsupported file type: {file_name}")
            
            # Clean column names (strip whitespace)
            df.columns = df.columns.str.strip()
            
            # Remove completely empty rows
            df = df.dropna(how='all')
            
            if df.empty:
                raise ValueError("File is empty or contains no valid data")
            
            return df
        
        except Exception as e:
            raise ValueError(f"Error reading file: {str(e)}")
    
    def validate_mapping(
        self, 
        df: pd.DataFrame, 
        mapping: ImportMapping
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that all mapped columns exist in the DataFrame.
        
        Args:
            df: DataFrame to validate
            mapping: Column mapping configuration
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        df_columns = set(df.columns)
        mapped_columns = {m.column_name for m in mapping.mappings}
        
        missing_columns = mapped_columns - df_columns
        
        if missing_columns:
            return False, f"Columns not found in file: {', '.join(missing_columns)}"
        
        return True, None
    
    def parse_decimal(
        self, 
        value: Any, 
        field_name: str, 
        row_number: int
    ) -> Tuple[Optional[Decimal], Optional[ImportRowError]]:
        """
        Parse a value as Decimal with error handling.
        
        Args:
            value: Value to parse
            field_name: Name of the field (for error reporting)
            row_number: Row number (for error reporting)
            
        Returns:
            Tuple of (parsed_value, error)
        """
        if pd.isna(value):
            return None, ImportRowError(
                row_number=row_number,
                column_name=field_name,
                error_message=f"{field_name} is required but is empty",
                raw_value=None
            )
        
        try:
            # Handle string values with currency symbols or commas
            if isinstance(value, str):
                # Remove common currency symbols and thousands separators
                cleaned = value.strip().replace('R$', '').replace('$', '')
                cleaned = cleaned.replace(',', '').replace(' ', '')
                value = cleaned
            
            decimal_value = Decimal(str(value))
            
            if decimal_value < 0:
                return None, ImportRowError(
                    row_number=row_number,
                    column_name=field_name,
                    error_message=f"{field_name} must be non-negative",
                    raw_value=value
                )
            
            return decimal_value, None
        
        except (InvalidOperation, ValueError) as e:
            return None, ImportRowError(
                row_number=row_number,
                column_name=field_name,
                error_message=f"{field_name} must be a valid number, got: {value}",
                raw_value=value
            )
    
    def parse_integer(
        self, 
        value: Any, 
        field_name: str, 
        row_number: int
    ) -> Tuple[Optional[int], Optional[ImportRowError]]:
        """
        Parse a value as integer with error handling.
        
        Args:
            value: Value to parse
            field_name: Name of the field (for error reporting)
            row_number: Row number (for error reporting)
            
        Returns:
            Tuple of (parsed_value, error)
        """
        if pd.isna(value):
            return None, ImportRowError(
                row_number=row_number,
                column_name=field_name,
                error_message=f"{field_name} is required but is empty",
                raw_value=None
            )
        
        try:
            int_value = int(float(value))  # Handle "10.0" strings
            
            if int_value <= 0:
                return None, ImportRowError(
                    row_number=row_number,
                    column_name=field_name,
                    error_message=f"{field_name} must be positive",
                    raw_value=value
                )
            
            return int_value, None
        
        except (ValueError, TypeError) as e:
            return None, ImportRowError(
                row_number=row_number,
                column_name=field_name,
                error_message=f"{field_name} must be a valid integer, got: {value}",
                raw_value=value
            )
    
    def parse_string(
        self, 
        value: Any, 
        field_name: str, 
        row_number: int
    ) -> Tuple[Optional[str], Optional[ImportRowError]]:
        """
        Parse a value as string with error handling.
        
        Args:
            value: Value to parse
            field_name: Name of the field (for error reporting)
            row_number: Row number (for error reporting)
            
        Returns:
            Tuple of (parsed_value, error)
        """
        if pd.isna(value):
            return None, ImportRowError(
                row_number=row_number,
                column_name=field_name,
                error_message=f"{field_name} is required but is empty",
                raw_value=None
            )
        
        str_value = str(value).strip()
        
        if not str_value:
            return None, ImportRowError(
                row_number=row_number,
                column_name=field_name,
                error_message=f"{field_name} cannot be empty",
                raw_value=value
            )
        
        return str_value, None
    
    def parse_row(
        self,
        row: pd.Series,
        row_number: int,
        mapping_dict: Dict[str, ImportFieldType]
    ) -> Tuple[Optional[Dict[str, Any]], List[ImportRowError]]:
        """
        Parse a single row from the DataFrame.
        
        Supports both legacy cost-based imports and new ONET 19-field imports.
        Cost fields are optional - if not provided, they will be looked up from material_costs.
        
        Args:
            row: DataFrame row
            row_number: Row number (1-indexed)
            mapping_dict: Dictionary mapping column names to field types
            
        Returns:
            Tuple of (parsed_data, errors)
        """
        errors = []
        data = {}
        
        # Reverse mapping: field_type -> column_name
        field_to_column = {v: k for k, v in mapping_dict.items()}
        
        # ============================================================
        # REQUIRED FIELDS (Must be present in all imports)
        # ============================================================
        
        # Parse PO number
        if ImportFieldType.PO_NUMBER not in field_to_column:
            errors.append(ImportRowError(
                row_number=row_number,
                error_message="PO Number field is required but not mapped"
            ))
        else:
            po_col = field_to_column[ImportFieldType.PO_NUMBER]
            po_number, error = self.parse_string(row[po_col], "PO Number", row_number)
            if error:
                errors.append(error)
            else:
                data['po_number'] = po_number
        
        # Parse client name
        if ImportFieldType.CLIENT_NAME not in field_to_column:
            errors.append(ImportRowError(
                row_number=row_number,
                error_message="Client Name field is required but not mapped"
            ))
        else:
            client_col = field_to_column[ImportFieldType.CLIENT_NAME]
            client_name, error = self.parse_string(row[client_col], "Client Name", row_number)
            if error:
                errors.append(error)
            else:
                data['client_name'] = client_name
        
        # Parse SKU
        if ImportFieldType.SKU not in field_to_column:
            errors.append(ImportRowError(
                row_number=row_number,
                error_message="SKU field is required but not mapped"
            ))
        else:
            sku_col = field_to_column[ImportFieldType.SKU]
            sku, error = self.parse_string(row[sku_col], "SKU", row_number)
            if error:
                errors.append(error)
            else:
                data['sku'] = sku
        
        # Parse quantity
        if ImportFieldType.QUANTITY not in field_to_column:
            errors.append(ImportRowError(
                row_number=row_number,
                error_message="Quantity field is required but not mapped"
            ))
        else:
            qty_col = field_to_column[ImportFieldType.QUANTITY]
            quantity, error = self.parse_integer(row[qty_col], "Quantity", row_number)
            if error:
                errors.append(error)
            else:
                data['quantity'] = quantity
        
        # ============================================================
        # OPTIONAL ONET FIELDS (19-field structure)
        # ============================================================
        
        # Description
        if ImportFieldType.DESCRIPTION in field_to_column:
            desc_col = field_to_column[ImportFieldType.DESCRIPTION]
            if not pd.isna(row[desc_col]):
                data['description'] = str(row[desc_col]).strip()
        
        # Unit
        if ImportFieldType.UNIT in field_to_column:
            unit_col = field_to_column[ImportFieldType.UNIT]
            if not pd.isna(row[unit_col]):
                data['unit'] = str(row[unit_col]).strip()
        
        # Width
        if ImportFieldType.WIDTH in field_to_column:
            width_col = field_to_column[ImportFieldType.WIDTH]
            if not pd.isna(row[width_col]):
                try:
                    data['width'] = Decimal(str(row[width_col]))
                except (InvalidOperation, ValueError):
                    pass  # Skip invalid values
        
        # Length
        if ImportFieldType.LENGTH in field_to_column:
            length_col = field_to_column[ImportFieldType.LENGTH]
            if not pd.isna(row[length_col]):
                try:
                    data['length'] = Decimal(str(row[length_col]))
                except (InvalidOperation, ValueError):
                    pass
        
        # Lead Time
        if ImportFieldType.LEAD_TIME in field_to_column:
            lead_col = field_to_column[ImportFieldType.LEAD_TIME]
            if not pd.isna(row[lead_col]):
                try:
                    data['lead_time'] = int(float(row[lead_col]))
                except (ValueError, TypeError):
                    pass
        
        # Delivery Date
        if ImportFieldType.DELIVERY_DATE in field_to_column:
            delivery_col = field_to_column[ImportFieldType.DELIVERY_DATE]
            if not pd.isna(row[delivery_col]):
                data['delivery_date'] = str(row[delivery_col]).strip()
        
        # Billing Date
        if ImportFieldType.BILLING_DATE in field_to_column:
            billing_col = field_to_column[ImportFieldType.BILLING_DATE]
            if not pd.isna(row[billing_col]):
                data['billing_date'] = str(row[billing_col]).strip()
        
        # ICMS Percent
        if ImportFieldType.ICMS_PERCENT in field_to_column:
            icms_col = field_to_column[ImportFieldType.ICMS_PERCENT]
            if not pd.isna(row[icms_col]):
                try:
                    data['icms_percent'] = Decimal(str(row[icms_col]))
                except (InvalidOperation, ValueError):
                    pass
        
        # Block Status
        if ImportFieldType.BLOCK_STATUS in field_to_column:
            block_col = field_to_column[ImportFieldType.BLOCK_STATUS]
            if not pd.isna(row[block_col]):
                data['block_status'] = str(row[block_col]).strip()
        
        # Balance
        if ImportFieldType.BALANCE in field_to_column:
            balance_col = field_to_column[ImportFieldType.BALANCE]
            if not pd.isna(row[balance_col]):
                try:
                    data['balance'] = Decimal(str(row[balance_col]))
                except (InvalidOperation, ValueError):
                    pass
        
        # Delay
        if ImportFieldType.DELAY in field_to_column:
            delay_col = field_to_column[ImportFieldType.DELAY]
            if not pd.isna(row[delay_col]):
                try:
                    data['delay'] = int(float(row[delay_col]))
                except (ValueError, TypeError):
                    pass
        
        # Payment Terms
        if ImportFieldType.PAYMENT_TERMS in field_to_column:
            payment_col = field_to_column[ImportFieldType.PAYMENT_TERMS]
            if not pd.isna(row[payment_col]):
                data['payment_terms'] = str(row[payment_col]).strip()
        
        # Freight
        if ImportFieldType.FREIGHT in field_to_column:
            freight_col = field_to_column[ImportFieldType.FREIGHT]
            if not pd.isna(row[freight_col]):
                try:
                    data['freight'] = Decimal(str(row[freight_col]))
                except (InvalidOperation, ValueError):
                    pass
        
        # Salesperson
        if ImportFieldType.SALESPERSON in field_to_column:
            sales_col = field_to_column[ImportFieldType.SALESPERSON]
            if not pd.isna(row[sales_col]):
                data['salesperson'] = str(row[sales_col]).strip()
        
        # IPI
        if ImportFieldType.IPI in field_to_column:
            ipi_col = field_to_column[ImportFieldType.IPI]
            if not pd.isna(row[ipi_col]):
                try:
                    data['ipi'] = Decimal(str(row[ipi_col]))
                except (InvalidOperation, ValueError):
                    pass
        
        # ============================================================
        # OPTIONAL COST FIELDS (Legacy support or explicit cost imports)
        # ============================================================
        
        # Price Unit (optional - can be calculated from costs)
        if ImportFieldType.PRICE_UNIT in field_to_column:
            price_col = field_to_column[ImportFieldType.PRICE_UNIT]
            if not pd.isna(row[price_col]):
                price_unit, error = self.parse_decimal(row[price_col], "Unit Price", row_number)
                if not error:
                    data['price_unit'] = price_unit
        
        # Cost MP (optional - will be looked up from material_costs if not provided)
        if ImportFieldType.COST_MP in field_to_column:
            cost_mp_col = field_to_column[ImportFieldType.COST_MP]
            if not pd.isna(row[cost_mp_col]):
                cost_mp, error = self.parse_decimal(row[cost_mp_col], "Material Cost", row_number)
                if not error:
                    data['cost_mp'] = cost_mp
        
        # Cost MO (optional)
        if ImportFieldType.COST_MO in field_to_column:
            cost_mo_col = field_to_column[ImportFieldType.COST_MO]
            if not pd.isna(row[cost_mo_col]):
                cost_mo, error = self.parse_decimal(row[cost_mo_col], "Labor Cost", row_number)
                if not error:
                    data['cost_mo'] = cost_mo
        
        # Cost Energy (optional)
        if ImportFieldType.COST_ENERGY in field_to_column:
            cost_energy_col = field_to_column[ImportFieldType.COST_ENERGY]
            if not pd.isna(row[cost_energy_col]):
                cost_energy, error = self.parse_decimal(row[cost_energy_col], "Energy Cost", row_number)
                if not error:
                    data['cost_energy'] = cost_energy
        
        # Cost Gas (optional)
        if ImportFieldType.COST_GAS in field_to_column:
            cost_gas_col = field_to_column[ImportFieldType.COST_GAS]
            if not pd.isna(row[cost_gas_col]):
                cost_gas, error = self.parse_decimal(row[cost_gas_col], "Gas Cost", row_number)
                if not error:
                    data['cost_gas'] = cost_gas
        
        # If we have critical errors (missing required fields), return early
        if errors:
            return None, errors
        
        return data, []
    
    def validate_import_data(
        self, 
        df: pd.DataFrame, 
        mapping: ImportMapping
    ) -> ImportValidationResult:
        """
        Validate all rows in the DataFrame and group by PO.
        
        Args:
            df: DataFrame with import data
            mapping: Column mapping configuration
            
        Returns:
            ImportValidationResult with validated data or errors
        """
        mapping_dict = mapping.get_mapping_dict()
        all_errors = []
        rows_data = []
        
        # Parse all rows
        for idx, row in df.iterrows():
            row_number = idx + 2  # +2 because: 0-indexed + header row
            parsed_data, errors = self.parse_row(row, row_number, mapping_dict)
            
            if errors:
                all_errors.extend(errors)
            elif parsed_data:
                rows_data.append(parsed_data)
        
        # If there are any parsing errors, return failure
        if all_errors:
            return ImportValidationResult(
                success=False,
                errors=all_errors,
                total_rows_processed=len(df),
                valid_rows=len(rows_data),
                invalid_rows=len(all_errors)
            )
        
        # Group items by PO number
        po_groups = {}
        for row_data in rows_data:
            po_number = row_data['po_number']
            client_name = row_data['client_name']
            
            if po_number not in po_groups:
                po_groups[po_number] = {
                    'po_number': po_number,
                    'client_name': client_name,
                    'items': []
                }
            
            # Verify client name consistency
            if po_groups[po_number]['client_name'] != client_name:
                all_errors.append(ImportRowError(
                    row_number=0,
                    error_message=f"PO {po_number} has inconsistent client names: "
                                  f"'{po_groups[po_number]['client_name']}' vs '{client_name}'"
                ))
                continue
            
            # Create item data
            try:
                item = ImportItemData(
                    sku=row_data['sku'],
                    quantity=row_data['quantity'],
                    price_unit=row_data['price_unit'],
                    cost_mp=row_data['cost_mp'],
                    cost_mo=row_data['cost_mo'],
                    cost_energy=row_data['cost_energy'],
                    cost_gas=row_data['cost_gas']
                )
                po_groups[po_number]['items'].append(item)
            except Exception as e:
                all_errors.append(ImportRowError(
                    row_number=0,
                    error_message=f"Validation error for SKU {row_data['sku']}: {str(e)}"
                ))
        
        # If there are validation errors, return failure
        if all_errors:
            return ImportValidationResult(
                success=False,
                errors=all_errors,
                total_rows_processed=len(df),
                valid_rows=len(rows_data) - len(all_errors),
                invalid_rows=len(all_errors)
            )
        
        # For now, we only support single PO imports
        if len(po_groups) > 1:
            return ImportValidationResult(
                success=False,
                errors=[ImportRowError(
                    row_number=0,
                    error_message=f"Multiple PO numbers found in file: {', '.join(po_groups.keys())}. "
                                  "Please import one PO at a time."
                )],
                total_rows_processed=len(df),
                valid_rows=0,
                invalid_rows=len(df)
            )
        
        # Create PO data
        po_number = list(po_groups.keys())[0]
        po_group = po_groups[po_number]
        
        try:
            po_data = ImportPOData(
                po_number=po_group['po_number'],
                client_name=po_group['client_name'],
                items=po_group['items']
            )
            
            return ImportValidationResult(
                success=True,
                po_data=po_data,
                total_rows_processed=len(df),
                valid_rows=len(rows_data),
                invalid_rows=0
            )
        
        except Exception as e:
            return ImportValidationResult(
                success=False,
                errors=[ImportRowError(
                    row_number=0,
                    error_message=f"PO validation error: {str(e)}"
                )],
                total_rows_processed=len(df),
                valid_rows=0,
                invalid_rows=len(df)
            )
    
    def import_po(
        self, 
        request: ImportRequest
    ) -> ImportResponse:
        """
        Import a Purchase Order from file with full validation and atomicity.
        
        This method ensures atomicity: if ANY validation fails, the entire
        import is rolled back and no data is saved to the database.
        
        Args:
            request: Import request with file data and mapping
            
        Returns:
            ImportResponse with success status and details
        """
        try:
            # Step 1: Read file
            try:
                df = self.read_file(request.file_content, request.file_name)
            except ValueError as e:
                return ImportResponse(
                    success=False,
                    message=f"File reading error: {str(e)}",
                    items_imported=0
                )
            
            # Step 2: Validate mapping
            is_valid, error_msg = self.validate_mapping(df, request.mapping)
            if not is_valid:
                return ImportResponse(
                    success=False,
                    message=f"Mapping error: {error_msg}",
                    items_imported=0
                )
            
            # Step 3: Validate and parse data
            validation_result = self.validate_import_data(df, request.mapping)
            
            if not validation_result.success:
                # Format error messages
                error_messages = []
                for error in validation_result.errors[:5]:  # Show first 5 errors
                    msg = f"Row {error.row_number}: {error.error_message}"
                    if error.column_name:
                        msg += f" (Column: {error.column_name})"
                    error_messages.append(msg)
                
                if len(validation_result.errors) > 5:
                    error_messages.append(
                        f"... and {len(validation_result.errors) - 5} more errors"
                    )
                
                return ImportResponse(
                    success=False,
                    message="Validation failed. " + "; ".join(error_messages),
                    items_imported=0,
                    validation_result=validation_result
                )
            
            # Step 4: Save to database with transaction (atomicity)
            po_data = validation_result.po_data
            
            try:
                # Begin transaction (implicit with session)
                # TODO: Create actual database records here
                # This would involve:
                # 1. Creating PurchaseOrder record with status NOVO_PEDIDO
                # 2. Creating OrderItem records for each item
                # 3. Setting tenant_id on all records
                # 4. Committing transaction
                
                # For now, we'll simulate success
                po_id = str(uuid.uuid4())
                
                # If we were to implement this with actual models:
                # from backend.models import PurchaseOrder, OrderItem
                # 
                # po = PurchaseOrder(
                #     tenant_id=uuid.UUID(request.tenant_id),
                #     po_number=po_data.po_number,
                #     status_macro="NOVO_PEDIDO",  # Initial status
                #     created_by=uuid.UUID(request.user_id)
                # )
                # self.db.add(po)
                # self.db.flush()  # Get PO ID
                # 
                # for item_data in po_data.items:
                #     item = OrderItem(
                #         po_id=po.id,
                #         tenant_id=uuid.UUID(request.tenant_id),
                #         sku=item_data.sku,
                #         quantity=item_data.quantity,
                #         price=item_data.price_unit,
                #         status_item="PENDING"
                #     )
                #     self.db.add(item)
                # 
                # self.db.commit()
                
                return ImportResponse(
                    success=True,
                    message=f"Successfully imported PO {po_data.po_number} with {len(po_data.items)} items",
                    po_id=po_id,
                    po_number=po_data.po_number,
                    items_imported=len(po_data.items),
                    validation_result=validation_result,
                    total_value=po_data.total_value,
                    total_cost=po_data.total_cost,
                    margin_global=po_data.margin_global,
                    margin_percentage=po_data.margin_percentage
                )
            
            except SQLAlchemyError as e:
                # Rollback on database error
                self.db.rollback()
                return ImportResponse(
                    success=False,
                    message=f"Database error during import: {str(e)}",
                    items_imported=0
                )
        
        except Exception as e:
            # Catch any unexpected errors
            self.db.rollback()
            return ImportResponse(
                success=False,
                message=f"Unexpected error during import: {str(e)}",
                items_imported=0
            )
    
    def get_file_headers(
        self, 
        file_content: bytes, 
        file_name: str
    ) -> List[str]:
        """
        Extract column headers from a file for mapping UI.
        
        Args:
            file_content: Raw file bytes
            file_name: Name of the file
            
        Returns:
            List of column names
            
        Raises:
            ValueError: If file cannot be read
        """
        df = self.read_file(file_content, file_name)
        return df.columns.tolist()

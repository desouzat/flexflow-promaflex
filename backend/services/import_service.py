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
from backend.utils.number_utils import clean_brazilian_number

def clean_integer_string(val: Any) -> Optional[str]:
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif s.count('.') > 1:
        s = s.replace('.', '')
    return s
from backend.schemas.import_schema import ImportFieldType

UNIT_VALUE_ALIASES = ["VlUnit", "Vl.Unit", "Vl Unit", "Preço Unitário", "Preco Unitario", "Unit Price", "Unit Value"]
ITEM_TOTAL_VALUE_ALIASES = ["Total Item", "Total do Item", "Item Total", "Valor do Item", "Valor Total Item", "Item Total Value", "Custo Total"]
PO_TOTAL_VALUE_ALIASES = ["Vl.Pedido", "Valor Total do Pedido", "Total do Pedido", "Valor Total Pedido", "Total Pedido", "PO Total", "PO Total Value"]

FIELD_ALIASES = {
    ImportFieldType.PO_NUMBER: ["Nº do Pedido", "Pedido", "Nº Pedido", "Num Pedido", "PO Number", "PO_Number"],
    ImportFieldType.CLIENT_NAME: ["Cliente", "Nome Cliente", "Client Name", "Client"],
    ImportFieldType.SKU: ["Id Produto", "SKU", "Código", "Cod", "Product SKU", "Item SKU"],
    ImportFieldType.QUANTITY: ["Qtd", "Quantidade", "Qty", "Quantity"],
    ImportFieldType.DESCRIPTION: ["Descr. Produto", "Descrição", "Descricao", "Description", "Desc"],
    ImportFieldType.UNIT: ["Unidade", "Un", "Unit"],
    ImportFieldType.WIDTH: ["Largura", "Width"],
    ImportFieldType.LENGTH: ["Comprimento", "Length"],
    ImportFieldType.LEAD_TIME: ["Lead Time", "LeadTime", "Prazo"],
    ImportFieldType.DELIVERY_DATE: ["Data Entrega", "Delivery Date", "Dt Entrega", "Dt.Entrega"],
    ImportFieldType.BILLING_DATE: ["Data Faturamento", "Billing Date", "Dt Faturamento", "Dt.Faturamento"],
    ImportFieldType.ICMS_PERCENT: ["% ICMS", "ICMS", "ICMS%"],
    ImportFieldType.IPI: ["IPI", "Vl. IPI"],
    ImportFieldType.FREIGHT: ["Frete", "Freight", "Vl.Frete"],
    ImportFieldType.PAYMENT_TERMS: ["Cond.Pgto", "Condição Pagamento", "Condicao Pagamento", "Payment Terms", "Pagamento"],
    ImportFieldType.UNIT_VALUE: UNIT_VALUE_ALIASES,
    ImportFieldType.ITEM_TOTAL_VALUE: ITEM_TOTAL_VALUE_ALIASES,
    ImportFieldType.PO_TOTAL_VALUE: PO_TOTAL_VALUE_ALIASES,
    ImportFieldType.BLOCK_STATUS: ["Bloqueio Faturamento", "Bloqueio", "Status Bloqueio", "Block Status", "Block"],
    ImportFieldType.BALANCE: ["Saldo", "Balance", "Saldo Devedor"],
    ImportFieldType.DELAY: ["Atraso", "Delay", "Dias Médio Atraso"],
    ImportFieldType.SALESPERSON: ["Vendedor", "Salesperson", "Sales Person"]
}



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
    
    def resolve_aliases(self, df: pd.DataFrame, mapping: ImportMapping) -> None:
        """
        Dynamically resolve missing columns in mapping using aliases.
        If a mapped column does not exist in the dataframe, search the dataframe's
        headers for any aliases matching the field type, and update the mapping.
        
        Flexible Header Matching: Ensures mapping logic is case-insensitive and trimmed.
        Validation Bypass: If a column is missing but has a valid alias present in the file,
        the mapping is updated so validation passes.
        """
        df_columns = list(df.columns)
        df_columns_stripped_lower = [str(col).strip().lower() for col in df_columns]
        
        for m in mapping.mappings:
            col_name_str = str(m.column_name).strip()
            
            # 1. Exact match (case-sensitive, trimmed)
            if col_name_str in df_columns:
                m.column_name = col_name_str
                continue
                
            # 2. Case-insensitive and trimmed match
            if col_name_str.lower() in df_columns_stripped_lower:
                idx = df_columns_stripped_lower.index(col_name_str.lower())
                m.column_name = df_columns[idx]
                continue
                
            # 3. Check aliases for this field type
            aliases = FIELD_ALIASES.get(m.field_type, [])
            for col in df_columns:
                col_str = str(col).strip()
                # Compare case-insensitively and trimmed
                if col_str.lower() in [a.strip().lower() for a in aliases]:
                    m.column_name = col
                    break
    
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
                df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
            
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
        Delegates all Brazilian currency normalization to clean_brazilian_number().

        Handles:
          - Native floats/ints (passed directly to Decimal)
          - Brazilian format strings: "R$ 13.335,00" → Decimal("13335.00")
          - Standard format strings: "13335.00" → Decimal("13335.00")
          - NaN / None → error record
          - Negative values → error record
          - Non-parsable strings → error record

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
            # Normalize via centralized utility (handles R$, BRL format, etc.)
            cleaned = clean_brazilian_number(value)

            if cleaned is None:
                # clean_brazilian_number returns None for negatives and invalid inputs.
                # Let's check if the input represents a negative number to throw a specific error.
                is_negative = False
                if value is not None and not pd.isna(value):
                    if isinstance(value, (int, float, Decimal)):
                        is_negative = value < 0
                    else:
                        s = str(value).strip().replace("R$", "").replace(" ", "")
                        if s.startswith("-"):
                            is_negative = True

                if is_negative:
                    error_message = f"{field_name} must be non-negative"
                else:
                    error_message = f"{field_name} must be a valid number, got: {value!r}"

                return None, ImportRowError(
                    row_number=row_number,
                    column_name=field_name,
                    error_message=error_message,
                    raw_value=str(value)
                )

            decimal_value = Decimal(cleaned)

            # Extra guard: clean_brazilian_number already rejects negatives,
            # but Decimal('-0') edge cases could slip through.
            if decimal_value < 0:
                return None, ImportRowError(
                    row_number=row_number,
                    column_name=field_name,
                    error_message=f"{field_name} must be non-negative",
                    raw_value=str(value)
                )

            return decimal_value, None

        except (InvalidOperation, ValueError) as e:
            return None, ImportRowError(
                row_number=row_number,
                column_name=field_name,
                error_message=f"{field_name} must be a valid number, got: {value!r}",
                raw_value=str(value)
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
            cleaned = clean_brazilian_number(value)
            val_to_parse = cleaned if cleaned is not None else value
            int_value = int(float(val_to_parse))  # Handle "10.0" strings
            
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
        
        for field_type, aliases in FIELD_ALIASES.items():
            if field_type not in field_to_column:
                # Search the series/row index (column headers) for matches
                for col in row.index:
                    col_str = str(col).strip()
                    if col_str in aliases or col_str.lower() in [a.lower() for a in aliases]:
                        field_to_column[field_type] = col
                        break
        
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
            quantity, error = self.parse_decimal(row[qty_col], "Quantity", row_number)
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
                    cleaned = clean_integer_string(row[lead_col])
                    val = cleaned if cleaned is not None else row[lead_col]
                    data['lead_time'] = int(float(val))
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
                    val_str = str(row[icms_col]).replace('%', '').strip()
                    cleaned = clean_brazilian_number(val_str)
                    if cleaned is not None:
                        data['icms_percent'] = Decimal(cleaned)
                    else:
                        data['icms_percent'] = Decimal(val_str)
                except (InvalidOperation, ValueError):
                    pass
        
        # Block Status
        if ImportFieldType.BLOCK_STATUS in field_to_column:
            block_col = field_to_column[ImportFieldType.BLOCK_STATUS]
            if not pd.isna(row[block_col]):
                val = str(row[block_col]).strip()
                if val.upper() == 'N':
                    data['block_status'] = 'LIBERADO'
                elif val.upper() == 'S':
                    data['block_status'] = 'BLOQUEADO'
                else:
                    data['block_status'] = val
        
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
                    cleaned = clean_integer_string(row[delay_col])
                    val = cleaned if cleaned is not None else row[delay_col]
                    data['delay'] = int(float(val))
                except (ValueError, TypeError):
                    pass
        
        # Payment Terms
        if ImportFieldType.PAYMENT_TERMS in field_to_column:
            payment_col = field_to_column[ImportFieldType.PAYMENT_TERMS]
            if not pd.isna(row[payment_col]):
                val = str(row[payment_col]).strip()
                if val.upper().endswith(' DDL'):
                    val = val[:-4].strip()
                elif val.upper().endswith('DDL'):
                    val = val[:-3].strip()
                data['payment_terms'] = val
        
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
                    cleaned = clean_brazilian_number(row[ipi_col])
                    if cleaned is not None:
                        data['ipi'] = Decimal(cleaned)
                    else:
                        data['ipi'] = Decimal(str(row[ipi_col]))
                except (InvalidOperation, ValueError):
                    pass
        
        # ============================================================
        # NEW: FINANCIAL VALUE FIELDS (22-field structure)
        # ============================================================
        
        # Unit Value (Vl.Unit)
        if ImportFieldType.UNIT_VALUE in field_to_column:
            unit_value_col = field_to_column[ImportFieldType.UNIT_VALUE]
            if not pd.isna(row[unit_value_col]):
                try:
                    # Delegate to centralized utility — correctly handles "13.335,50" → "13335.50"
                    cleaned = clean_brazilian_number(row[unit_value_col])
                    if cleaned is not None:
                        data['unit_value'] = Decimal(cleaned)
                except (InvalidOperation, ValueError):
                    pass  # Skip invalid values

        # Item Total Value (Total Item)
        if ImportFieldType.ITEM_TOTAL_VALUE in field_to_column:
            item_total_col = field_to_column[ImportFieldType.ITEM_TOTAL_VALUE]
            if not pd.isna(row[item_total_col]):
                try:
                    # Delegate to centralized utility — correctly handles "13.335,50" → "13335.50"
                    cleaned = clean_brazilian_number(row[item_total_col])
                    if cleaned is not None:
                        data['item_total_value'] = Decimal(cleaned)
                except (InvalidOperation, ValueError):
                    pass  # Skip invalid values

        # PO Total Value (Valor Total do Pedido)
        if ImportFieldType.PO_TOTAL_VALUE in field_to_column:
            po_total_col = field_to_column[ImportFieldType.PO_TOTAL_VALUE]
            if not pd.isna(row[po_total_col]):
                try:
                    # Delegate to centralized utility — correctly handles "13.335,50" → "13335.50"
                    cleaned = clean_brazilian_number(row[po_total_col])
                    if cleaned is not None:
                        data['po_total_value'] = Decimal(cleaned)
                except (InvalidOperation, ValueError):
                    pass  # Skip invalid values
        
        # ============================================================
        # OPTIONAL COST FIELDS (Legacy support or explicit cost imports)
        # ============================================================
        
        # Price Unit (optional - can be calculated from costs)
        if ImportFieldType.PRICE_UNIT in field_to_column:
            price_col = field_to_column[ImportFieldType.PRICE_UNIT]
            if not pd.isna(row[price_col]):
                price_unit, error = self.parse_decimal(row[price_col], "Unit Price", row_number)
                if error:
                    errors.append(error)
                else:
                    data['price_unit'] = price_unit
        
        # Cost MP (optional - will be looked up from material_costs if not provided)
        if ImportFieldType.COST_MP in field_to_column:
            cost_mp_col = field_to_column[ImportFieldType.COST_MP]
            if not pd.isna(row[cost_mp_col]):
                cost_mp, error = self.parse_decimal(row[cost_mp_col], "Material Cost", row_number)
                if error:
                    errors.append(error)
                else:
                    data['cost_mp'] = cost_mp
        
        # Cost MO (optional)
        if ImportFieldType.COST_MO in field_to_column:
            cost_mo_col = field_to_column[ImportFieldType.COST_MO]
            if not pd.isna(row[cost_mo_col]):
                cost_mo, error = self.parse_decimal(row[cost_mo_col], "Labor Cost", row_number)
                if error:
                    errors.append(error)
                else:
                    data['cost_mo'] = cost_mo
        
        # Cost Energy (optional)
        if ImportFieldType.COST_ENERGY in field_to_column:
            cost_energy_col = field_to_column[ImportFieldType.COST_ENERGY]
            if not pd.isna(row[cost_energy_col]):
                cost_energy, error = self.parse_decimal(row[cost_energy_col], "Energy Cost", row_number)
                if error:
                    errors.append(error)
                else:
                    data['cost_energy'] = cost_energy
        
        # Cost Gas (optional)
        if ImportFieldType.COST_GAS in field_to_column:
            cost_gas_col = field_to_column[ImportFieldType.COST_GAS]
            if not pd.isna(row[cost_gas_col]):
                cost_gas, error = self.parse_decimal(row[cost_gas_col], "Gas Cost", row_number)
                if error:
                    errors.append(error)
                else:
                    data['cost_gas'] = cost_gas
        
        # If we have critical errors (missing required fields), return early
        if errors:
            return None, errors
        
        return data, []
    
    def validate_import_data(
        self,
        df: pd.DataFrame,
        mapping: ImportMapping,
        tenant_id: Optional[str] = None
    ) -> ImportValidationResult:
        """
        Validate all rows in the DataFrame and group by PO.
        Supports multiple PO numbers in a single file.
        
        Args:
            df: DataFrame with import data
            mapping: Column mapping configuration
            
        Returns:
            ImportValidationResult with validated data or errors
        """
        self.resolve_aliases(df, mapping)
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
                    'items': [],
                    'po_total_value': row_data.get('po_total_value')  # Capture PO-level total from first row
                }
            
            # Verify client name consistency within each PO
            if po_groups[po_number]['client_name'] != client_name:
                all_errors.append(ImportRowError(
                    row_number=0,
                    error_message=f"PO {po_number} has inconsistent client names: "
                                  f"'{po_groups[po_number]['client_name']}' vs '{client_name}'"
                ))
                continue
            
            # Create item data
            # Use .get() for optional cost fields to avoid KeyError
            try:
                item = ImportItemData(
                    sku=row_data['sku'],
                    quantity=row_data['quantity'],
                    price_unit=row_data.get('price_unit'),
                    cost_mp=row_data.get('cost_mp'),
                    cost_mo=row_data.get('cost_mo'),
                    cost_energy=row_data.get('cost_energy'),
                    cost_gas=row_data.get('cost_gas'),
                    # Include ONET fields if present
                    description=row_data.get('description'),
                    unit=row_data.get('unit'),
                    width=row_data.get('width'),
                    length=row_data.get('length'),
                    lead_time=row_data.get('lead_time'),
                    delivery_date=row_data.get('delivery_date'),
                    billing_date=row_data.get('billing_date'),
                    icms_percent=row_data.get('icms_percent'),
                    block_status=row_data.get('block_status'),
                    balance=row_data.get('balance'),
                    delay=row_data.get('delay'),
                    payment_terms=row_data.get('payment_terms'),
                    freight=row_data.get('freight'),
                    salesperson=row_data.get('salesperson'),
                    ipi=row_data.get('ipi'),
                    # NEW: Financial value fields
                    unit_value=row_data.get('unit_value'),
                    item_total_value=row_data.get('item_total_value')
                )
                po_groups[po_number]['items'].append(item)
            except Exception as e:
                all_errors.append(ImportRowError(
                    row_number=0,
                    error_message=f"Validation error for SKU {row_data.get('sku', 'UNKNOWN')}: {str(e)}"
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
        
        # Create PO data list for all POs found
        po_data_list = []
        try:
            for po_number, po_group in po_groups.items():
                business_unit = None
                if tenant_id:
                    from backend.models import ClientPreference
                    from sqlalchemy import select
                    import uuid
                    tenant_uuid = uuid.UUID(str(tenant_id))
                    # DATABASE LOOKUP: SELECT business_unit FROM client_preferences WHERE tenant_id = :tenant_id AND client_name = :client_name
                    stmt = select(ClientPreference).where(
                        ClientPreference.tenant_id == tenant_uuid,
                        ClientPreference.client_name == po_group['client_name']
                    )
                    pref = self.db.execute(stmt).scalar_one_or_none()
                    if pref:
                        business_unit = pref.business_unit
                
                if not business_unit:
                    from backend.services.client_mapping_service import ClientMappingService
                    business_unit = ClientMappingService.classify_client(po_group['client_name'])

                po_data = ImportPOData(
                    po_number=po_group['po_number'],
                    client_name=po_group['client_name'],
                    business_unit=business_unit,
                    items=po_group['items'],
                    po_total_value=po_group.get('po_total_value')  # Include PO-level total
                )
                po_data_list.append(po_data)
            
            # For backward compatibility, if there's only one PO, also set po_data
            single_po_data = po_data_list[0] if len(po_data_list) == 1 else None
            
            return ImportValidationResult(
                success=True,
                po_data=single_po_data,  # Legacy single PO support
                po_data_list=po_data_list,  # Multi-PO support
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
        Import Purchase Orders from file with full validation and atomicity.
        Supports multiple PO numbers in a single file.
        
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
            self.resolve_aliases(df, request.mapping)
            is_valid, error_msg = self.validate_mapping(df, request.mapping)
            if not is_valid:
                return ImportResponse(
                    success=False,
                    message=f"Mapping error: {error_msg}",
                    items_imported=0
                )
            
            # Step 3: Validate and parse data
            validation_result = self.validate_import_data(df, request.mapping, tenant_id=request.tenant_id)
            
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
            
            # Step 4a: Mesa de Conferência — Financial Integrity Check (NON-BLOCKING WARNING)
            # ─────────────────────────────────────────────────────────────────────
            # DECISION (2026-06-11, Thiago — Solutions Engineer):
            #   The hard financial block was disabled because it caused operational
            #   stoppage when source Excel files had rounding or IPI distribution
            #   differences that do not represent actual data integrity problems.
            #
            # Previous behaviour (DISABLED):
            #   → return ImportResponse(success=False, message="❌ Bloqueio de
            #     Integridade Financeira...") for any Σ(item_total_value) ≠ po_total_value
            #
            # Current behaviour (NON-BLOCKING WARNING):
            #   → The mismatch is detected and its description is stored in
            #     po_data.integrity_error_message (already set by ImportPOData validator).
            #   → A "AVISO DO SISTEMA" prefix is prepended so the Mesa de Conferência
            #     UI can display the warning badge without blocking the import flow.
            #   → The PO is imported normally; has_integrity_error=True is forwarded
            #     to the frontend (lines 984-985 below) for visual flagging.
            #
            # To re-enable as a hard block in the future: uncomment the
            # `if integrity_errors: return ImportResponse(success=False, ...)` below.
            # ─────────────────────────────────────────────────────────────────────
            for po_data in validation_result.po_data_list or []:
                if po_data.has_integrity_error and po_data.integrity_error_message:
                    # Prepend a clear system warning marker so the UI and audit
                    # trail can distinguish auto-detected mismatches from other notes.
                    if not po_data.integrity_error_message.startswith("AVISO DO SISTEMA"):
                        po_data.integrity_error_message = (
                            "AVISO DO SISTEMA: PO importada com divergência financeira — "
                            + po_data.integrity_error_message
                        )
                    print(
                        f"[FINANCIAL WARNING] PO {po_data.po_number}: "
                        f"{po_data.integrity_error_message}",
                        flush=True
                    )

            # ── Hard-block (DISABLED) ─────────────────────────────────────────
            # if integrity_errors:
            #     return ImportResponse(
            #         success=False,
            #         message=(
            #             "❌ Bloqueio de Integridade Financeira (Mesa de Conferência): "
            #             + " | ".join(integrity_errors)
            #         ),
            #         items_imported=0
            #     )
            # ─────────────────────────────────────────────────────────────────

            # Step 4: Prepare response with multi-PO support
            po_data_list = validation_result.po_data_list or []
            total_items = sum(len(po.items) for po in po_data_list)
            
            # Build PO list for frontend
            po_list = []
            for po_data in po_data_list:
                po_list.append({
                    'po_number': po_data.po_number,
                    'client_name': po_data.client_name,
                    'business_unit': po_data.business_unit,
                    'items': [item.model_dump() for item in po_data.items],
                    'total_value': float(po_data.total_value) if po_data.total_value else None,
                    'total_cost': float(po_data.total_cost) if po_data.total_cost else None,
                    'margin_global': float(po_data.margin_global) if po_data.margin_global else None,
                    'margin_percentage': float(po_data.margin_percentage) if po_data.margin_percentage else None,
                    'po_total_value': float(po_data.po_total_value) if po_data.po_total_value is not None else None,
                    'has_integrity_error': po_data.has_integrity_error,
                    'integrity_error_message': po_data.integrity_error_message
                })
            
            # For backward compatibility with single PO
            if len(po_data_list) == 1:
                single_po = po_data_list[0]
                return ImportResponse(
                    success=True,
                    message=f"Successfully imported PO {single_po.po_number} with {len(single_po.items)} items",
                    po_id=str(uuid.uuid4()),
                    po_number=single_po.po_number,
                    client_name=single_po.client_name,
                    items=[item.model_dump() for item in single_po.items],
                    items_imported=len(single_po.items),
                    total_pos=1,
                    po_list=po_list,
                    validation_result=validation_result,
                    total_value=single_po.total_value,
                    total_cost=single_po.total_cost,
                    margin_global=single_po.margin_global,
                    margin_percentage=single_po.margin_percentage
                )
            else:
                # Multiple POs
                po_numbers = [po.po_number for po in po_data_list]
                return ImportResponse(
                    success=True,
                    message=f"Successfully imported {len(po_data_list)} POs ({', '.join(po_numbers)}) with {total_items} total items",
                    items_imported=total_items,
                    total_pos=len(po_data_list),
                    po_list=po_list,
                    validation_result=validation_result
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

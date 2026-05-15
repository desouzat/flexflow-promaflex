# Frontend Null-Safety Fix - Multi-PO Support

## Issue
Frontend crashed with `TypeError: Cannot read properties of undefined (reading 'some')` at `hasErrors (ImportPage.jsx:285:34)` when uploading a 50-row multi-PO file.

## Root Cause
The `hasErrors()` function and several other functions were trying to access `stagingData.items` directly, but in the multi-PO structure, items are nested inside `stagingData.po_list[].items`. The code was not null-safe and didn't account for the array structure.

## Fixes Applied

### 1. **hasErrors() Function** (Line 283-289)
**Before:**
```javascript
const hasErrors = () => {
    if (!stagingData) return false
    return stagingData.items.some(item => validateItem(item).length > 0)
}
```

**After:**
```javascript
const hasErrors = () => {
    if (!stagingData || !stagingData.po_list || !Array.isArray(stagingData.po_list)) return false
    
    // Check all items across all POs
    return stagingData.po_list.some(po => 
        Array.isArray(po.items) && po.items.some(item => validateItem(item).length > 0)
    )
}
```

### 2. **handleTogglePersonalized() Function** (Line 174-183)
**Before:** Accessed `prev.items` directly
**After:** Iterates through `prev.po_list` and maps items within each PO with full null-safety checks

### 3. **handleToggleNewClient() Function** (Line 185-194)
**Before:** Accessed `prev.items` directly
**After:** Iterates through `prev.po_list` and maps items within each PO with full null-safety checks

### 4. **handleNotesChange() Function** (Line 196-205)
**Before:** Accessed `prev.items` directly
**After:** Iterates through `prev.po_list` and maps items within each PO with full null-safety checks

### 5. **handleFileUpload() Function** (Line 235-249)
**Before:** Updated `prev.items` directly
**After:** Iterates through `prev.po_list` and updates items within each PO with full null-safety checks

### 6. **handleRemoveAttachment() Function** (Line 256-265)
**Before:** Updated `prev.items` directly
**After:** Iterates through `prev.po_list` and updates items within each PO with full null-safety checks

### 7. **getPaginatedItems() Function** (Line 416-426)
**Before:**
```javascript
const getPaginatedItems = () => {
    if (!stagingData || !stagingData.po_list || !stagingData.po_list[selectedPOIndex]) return []
    const currentPO = stagingData.po_list[selectedPOIndex]
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
    const endIndex = startIndex + ITEMS_PER_PAGE
    return currentPO.items.slice(startIndex, endIndex)
}
```

**After:**
```javascript
const getPaginatedItems = () => {
    if (!stagingData || !stagingData.po_list || !Array.isArray(stagingData.po_list)) return []
    if (!stagingData.po_list[selectedPOIndex]) return []
    
    const currentPO = stagingData.po_list[selectedPOIndex]
    if (!currentPO.items || !Array.isArray(currentPO.items)) return []
    
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
    const endIndex = startIndex + ITEMS_PER_PAGE
    return currentPO.items.slice(startIndex, endIndex)
}
```

### 8. **getCurrentPO() Function** (Line 428-431)
**Before:**
```javascript
const getCurrentPO = () => {
    if (!stagingData || !stagingData.po_list) return null
    return stagingData.po_list[selectedPOIndex]
}
```

**After:**
```javascript
const getCurrentPO = () => {
    if (!stagingData || !stagingData.po_list || !Array.isArray(stagingData.po_list)) return null
    return stagingData.po_list[selectedPOIndex] || null
}
```

### 9. **totalPages Calculation** (Line 434)
**Before:**
```javascript
const totalPages = currentPO ? Math.ceil(currentPO.items.length / ITEMS_PER_PAGE) : 0
```

**After:**
```javascript
const totalPages = currentPO && Array.isArray(currentPO.items) ? Math.ceil(currentPO.items.length / ITEMS_PER_PAGE) : 0
```

### 10. **handleNextPO() Function** (Line 449-454)
**Before:**
```javascript
const handleNextPO = () => {
    if (stagingData && stagingData.po_list) {
        setSelectedPOIndex(prev => Math.min(stagingData.po_list.length - 1, prev + 1))
        setCurrentPage(1)
    }
}
```

**After:**
```javascript
const handleNextPO = () => {
    if (stagingData && stagingData.po_list && Array.isArray(stagingData.po_list)) {
        setSelectedPOIndex(prev => Math.min(stagingData.po_list.length - 1, prev + 1))
        setCurrentPage(1)
    }
}
```

### 11. **Items Count Display** (Line 639)
**Before:**
```javascript
Itens do Pedido ({currentPO.items.length} total)
```

**After:**
```javascript
Itens do Pedido ({currentPO && Array.isArray(currentPO.items) ? currentPO.items.length : 0} total)
```

## Key Principles Applied

1. **Null-Safety First**: Every array access is now guarded with `Array.isArray()` checks
2. **Multi-PO Structure**: All functions now iterate through `po_list` instead of accessing `items` directly
3. **Defensive Programming**: Return early with safe defaults (empty arrays, null) when data is missing
4. **Data Structure Sync**: Frontend now correctly handles the backend's `po_list` structure

## Expected Behavior After Fix

✅ **No more crashes** when uploading multi-PO files
✅ **"Múltiplos Pedidos Detectados" banner** displays correctly
✅ **PO navigation** works (Previous/Next buttons)
✅ **Item pagination** works within each PO
✅ **Toggle functions** (Personalized, New Client) work across all POs
✅ **File attachments** can be uploaded and removed
✅ **Validation errors** are detected across all POs

## Testing Checklist

- [ ] Upload 50-row multi-PO file
- [ ] Verify "Múltiplos Pedidos Detectados" banner appears
- [ ] Navigate between POs using Previous/Next buttons
- [ ] Verify item count displays correctly for each PO
- [ ] Toggle "Personalizado" checkbox on items
- [ ] Toggle "Cliente Novo" checkbox on items
- [ ] Add customization notes
- [ ] Upload attachments
- [ ] Remove attachments
- [ ] Verify pagination works (10 items per page)
- [ ] Verify error validation works across all POs

## Files Modified

- `frontend/src/pages/ImportPage.jsx` - Added comprehensive null-safety checks for multi-PO support

## Status

✅ **READY FOR TESTING** - All null-safety issues resolved. Frontend should now handle multi-PO uploads without crashes.

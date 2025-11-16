# Customer Return Flow - Item-Based Tracking

## Overview
This document explains how customer returns of sold items are handled with automatic inventory updates.

## Flow Diagram

```
Customer buys 2 iPhones (ITEM001, ITEM002)
    ↓
Items marked as "sold" with order_id
    ↓
iPhone product quantity: 5 → 3
    ↓
Customer returns 2 items
    ↓
Check return reason & returnability
    ↓
    ├─ Damaged & Returnable to Vendor → Status: "return_to_vendor"
    ├─ Damaged & NOT Returnable → Status: "damaged" (Loss)
    └─ Not Damaged → Status: "available" (Back to inventory)
    ↓
Update items status
    ↓
Auto-update product quantity (count available items)
    ↓
iPhone product quantity updated accordingly
```

## Example Scenarios

### Scenario 1: Normal Return (No Damage)
**Initial State:**
- Product: iPhone (PROD001) - Quantity: 5
- Items: ITEM001, ITEM002, ITEM003, ITEM004, ITEM005 (all "available")

**Customer buys 2 iPhones (Order: ORD123):**
```json
{
  "order_id": "ORD123",
  "product_id": "PROD001",
  "quantity": 2
}
```
- ITEM001, ITEM002 → status: "sold", sold_order_id: "ORD123"
- iPhone quantity: 5 → 3 ✅

**Customer returns 2 iPhones (Reason: "Changed mind"):**
```json
{
  "order_id": "ORD123",
  "product_id": "PROD001",
  "return_quantity": 2,
  "reason": "Changed mind"
}
```
**Result:**
- ITEM001, ITEM002 → status: "available", sold_order_id: null
- Destination: **Inventory** ✅
- iPhone quantity: 3 → 5 ✅

---

### Scenario 2: Damaged & Returnable to Vendor
**Customer returns 2 iPhones (Reason: "Damage on arrival", Returnable: Yes):**
```json
{
  "order_id": "ORD123",
  "product_id": "PROD001",
  "return_quantity": 2,
  "reason": "Damage on arrival",
  "is_seller_returnable": true
}
```
**Result:**
- ITEM001, ITEM002 → status: "return_to_vendor"
- Destination: **ReturnToVendor** 📦
- iPhone quantity: 3 (no change, items not available) ✅
- Items tracked for vendor return processing

---

### Scenario 3: Damaged & NOT Returnable (Loss)
**Customer returns 2 iPhones (Reason: "Damage on arrival", Returnable: No):**
```json
{
  "order_id": "ORD123",
  "product_id": "PROD001",
  "return_quantity": 2,
  "reason": "Damage on arrival",
  "is_seller_returnable": false
}
```
**Result:**
- ITEM001, ITEM002 → status: "damaged"
- Destination: **LossOrders** ⚠️
- iPhone quantity: 3 (no change, items not available) ✅
- Items tracked as loss

---

## API Function

### `handle_customer_return()`
Located in: `app/services/admin_inventory_service.py`

**Parameters:**
```python
order_id: str              # Original sales order ID
product_id: str            # Product ID (e.g., "PROD001")
return_quantity: int       # Number of items being returned
return_reason: str         # Reason for return
store_id: str              # Store identifier
is_seller_returnable: bool # Can be returned to vendor?
```

**Logic:**
1. **Find sold items** from the order with status "sold"
2. **Determine destination** based on reason:
   - `"Damage on arrival"` + `is_seller_returnable=true` → `"return_to_vendor"`
   - `"Damage on arrival"` + `is_seller_returnable=false` → `"damaged"`
   - Any other reason → `"available"`
3. **Update item status** with return tracking
4. **Auto-update product quantity** by counting available items
5. **Return summary** with inventory updates

**Response:**
```json
{
  "message": "2 items returned and processed",
  "product_id": "PROD001",
  "return_reason": "Changed mind",
  "destination": "Inventory",
  "items_returned": [
    {
      "item_id": "ITEM001",
      "new_status": "available",
      "destination": "Inventory"
    },
    {
      "item_id": "ITEM002",
      "new_status": "available",
      "destination": "Inventory"
    }
  ],
  "inventory_updated": {
    "available_quantity": 5,
    "damaged_count": 0,
    "return_to_vendor_count": 0
  }
}
```

---

## Integration with validate_return_order()

The `validate_return_order()` function in `procurement_return_validation_services.py` now automatically detects customer returns:

**Detection Logic:**
```python
# Check if order_id exists and has sold items
if order_id:
    sold_items_count = await db.ProductItems.count_documents({
        "product_id": product_id,
        "sold_order_id": order_id,
        "status": "sold"
    })
    is_customer_return = sold_items_count > 0
```

**Automatic Routing:**
- If customer return detected → Use `handle_customer_return()` (item-based)
- Otherwise → Use old logic (vendor returns, new inventory)

---

## Item Status Values

| Status | Meaning | Counted in Inventory Quantity |
|--------|---------|------------------------------|
| `available` | In stock, ready to sell | ✅ Yes |
| `sold` | Sold to customer | ❌ No |
| `damaged` | Damaged/Loss | ❌ No |
| `return_to_vendor` | Being returned to vendor | ❌ No |
| `removed` | Removed from inventory | ❌ No |

---

## Key Benefits

✅ **Automatic Quantity Updates**: Product quantity = count of available items  
✅ **Full Item History**: Track each item's journey (sold → returned → available)  
✅ **Smart Routing**: Returns go to correct destination (Inventory/Vendor/Loss)  
✅ **No Manual Calculations**: System automatically counts and updates  
✅ **Audit Trail**: Every item tracks when sold, when returned, and why  

---

## Testing Examples

### Test 1: Normal Return
```bash
# 1. Sell 2 items
POST /api/sales/orders
{
  "product_id": "PROD001",
  "quantity": 2
}

# 2. Check inventory
GET /api/admin/products/PROD001
# Expected: quantity decreased by 2

# 3. Return 2 items
POST /api/returns/validate
{
  "return_id": "RET001",
  "order_id": "ORD123",
  "reason": "Changed mind"
}

# 4. Check inventory again
GET /api/admin/products/PROD001
# Expected: quantity increased by 2 (back to original)
```

### Test 2: Damaged Return
```bash
# Same steps but with:
{
  "reason": "Damage on arrival",
  "is_seller_returnable": false
}

# Expected: 
# - Items marked as "damaged"
# - Quantity does NOT increase
# - Items tracked in LossOrders
```

---

## Database Structure

### Inventory Collection
```json
{
  "product_id": "PROD001",
  "product_name": "iPhone 15",
  "quantity": 5,  // Auto-calculated from available items
  "status": "Stock-in",
  "store_id": "STR001"
}
```

### ProductItems Collection
```json
{
  "item_id": "ITEM001",
  "product_id": "PROD001",
  "status": "available",  // or "sold", "damaged", "return_to_vendor"
  "sold_order_id": null,  // Set when sold, cleared when returned to inventory
  "sold_at": null,
  "returned_at": null,
  "return_reason": null,
  "store_id": "STR001"
}
```

---

## Summary

The customer return system now:
1. ✅ Detects if return is from a sold order (item-based)
2. ✅ Updates item status based on return reason
3. ✅ Automatically updates product quantity
4. ✅ Routes items to correct destination
5. ✅ Maintains complete audit trail

**Result**: Seamless returns with automatic inventory synchronization! 🎉

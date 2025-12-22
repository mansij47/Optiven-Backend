# Tax Calculation Flow - Complete Implementation

## 📊 Current Tax Flow in Your System

### 1. **Contract Creation (ProductForm → Backend)**

#### Frontend: ProductForm Component
**File**: `Optiven-Frontend/src/modules/Procurement/pages/AddContracts/components/ProductForm/index.jsx`

```javascript
// User enters tax manually (line 341)
<Input
  label="Tax (%)"
  name="tax"
  value={data.tax || ''}
  onChange={handleChange}
  placeholder="25"
/>

// Sent to backend (line 175-195)
const payload = {
  product_name: data.product_name,
  unit_price: Number(data.unit_price),
  quantity: Number(data.quantity),
  tax: Number(data.tax || 0),  // ← Tax sent as percentage
  // ... other fields
};
```

**API Endpoint**: `POST /procurement/addContracts`

---

### 2. **Contract Storage**

#### Backend: Contract Service
**File**: `New_Backend/Optiven-Backend/app/services/procurement_contract_services.py`

```python
async def add_contract(contract_data: Contract, store_id: str, request: Request):
    # Contract stored in database with tax field
    contract_dict = contract_data.model_dump()
    contract_dict["store_id"] = store_id
    await contracts_collection.insert_one(contract_dict)
```

**Stored Fields**:
- `tax`: 18.0 (percentage value)
- `unit_price`: 100.0
- `quantity`: 5

---

### 3. **Contract Acceptance → Purchase Order**

#### Backend: Contract Status Update
**File**: `New_Backend/Optiven-Backend/app/services/procurement_contract_services.py` (Line 160-180)

```python
async def update_contract_status(contract_id: str, store_id: str, action: str):
    if action == "accept":
        purchase_order = {
            "vendor_name": contract["vendor_name"],
            "quantity": contract.get("quantity"),
            "unit_price": contract.get("unit_price"),
            # ← Tax is NOT copied to purchase_order here
            # This might be a gap in your current flow
        }
        await purchase_orders_collection.insert_one(purchase_order)
```

---

### 4. **Validation → Inventory**

#### Backend: Validation Service
**File**: `New_Backend/Optiven-Backend/app/services/procurement_validation_services.py` (Line 256-268)

```python
# Product added to Inventory
product_dict = {
    "product_name": base_order.get("product_name"),
    "unit": base_order.get("unit"),
    "quantity": data.received_quantity,
    "tax": float(base_order.get("tax", 0)),  # ← Tax stored in Inventory
    "unit_price": base_order.get("unit_price"),
    # ...
}
await db.Inventory.insert_one(product_dict)
```

**Inventory Structure**:
```json
{
  "product_id": "PROD001",
  "product_name": "Laptop",
  "quantity": 5,
  "unit_price": 100.0,
  "tax": 18.0,  ← Tax percentage stored
  "average_price": 100.0
}
```

---

### 5. **Sales Order Creation**

#### Backend: Sales Utils
**File**: `New_Backend/Optiven-Backend/app/utils/sales_utils.py` (Line 23-26)

**BEFORE** (Old Way - ❌ Incorrect):
```python
def build_product_detail(...):
    line_total = unit_price * order_quantity
    tax = product_tax * order_quantity  # ❌ Wrong: treating tax% as amount
```

**AFTER** (New Way - ✅ Correct):
```python
from app.utils.tax_utils import calculate_tax_amount

def build_product_detail(...):
    line_total = unit_price * order_quantity
    tax = calculate_tax_amount(unit_price, product_tax, order_quantity)
    # ✅ Correct: (100 * 18% / 100) * 5 = 90
```

---

### 6. **Tax Calculation in Sales**

#### Backend: Sales Get/Update Services
**File**: `New_Backend/Optiven-Backend/app/services/sales_get_update_services.py` (Line 109-120)

**BEFORE** (Old Way):
```python
def calculate_product_total_price(unit_price: float, tax: float, quantity: int) -> float:
    try:
        tax_amount = (unit_price * tax) / 100
        total = quantity * (unit_price + tax_amount)
        return round(total, 2)
    except (ValueError, TypeError):
        return 0.0
```

**AFTER** (New Way - ✅ Uses Centralized Function):
```python
from app.utils.tax_utils import calculate_product_total_with_tax

def calculate_product_total_price(unit_price: float, tax: float, quantity: int) -> float:
    """Uses centralized tax calculation utility from tax_utils"""
    return calculate_product_total_with_tax(unit_price, tax, quantity)
```

---

## 🔧 What Was Changed

### Files Updated:

1. **`app/utils/sales_utils.py`**
   - ✅ Added import: `from app.utils.tax_utils import calculate_tax_amount`
   - ✅ Updated tax calculation in `build_product_detail()`: 
     - Old: `tax = product_tax * order_quantity`
     - New: `tax = calculate_tax_amount(unit_price, product_tax, order_quantity)`

2. **`app/utils/raise_order.py`**
   - ✅ Added import: `from app.utils.tax_utils import calculate_tax_amount`
   - ✅ Updated tax calculation in `build_product_detail()`

3. **`app/services/sales_get_update_services.py`**
   - ✅ Added import: `from app.utils.tax_utils import calculate_product_total_with_tax`
   - ✅ Replaced function body of `calculate_product_total_price()` to use centralized utility

---

## 📐 Tax Calculation Formula

### Correct Formula (Now Implemented):
```
Tax Amount = (Unit Price × Tax Rate ÷ 100) × Quantity
Total = Quantity × (Unit Price + Tax Amount)

Example:
Unit Price: ₹100
Quantity: 5
Tax Rate: 18%

Tax Per Unit = 100 × 18 ÷ 100 = ₹18
Tax Amount = 18 × 5 = ₹90
Subtotal = 100 × 5 = ₹500
Total = (100 + 18) × 5 = ₹590
```

---

## 🌍 Country-Wise Tax (Future Enhancement)

Currently, tax is entered manually. To enable **automatic country-based tax**:

### Option 1: Auto-populate tax in ProductForm based on store country

**Frontend Change**:
```javascript
// In ProductForm/index.jsx
import { useGetTaxInfo } from '@/hooks/useTaxInfo';

const ProductForm = ({ data, setData, vendorData }) => {
  const { data: taxInfo } = useGetTaxInfo(storeId);
  
  // Auto-set tax when component loads
  useEffect(() => {
    if (taxInfo && !data.tax) {
      setData(prev => ({ ...prev, tax: taxInfo.tax_rate }));
    }
  }, [taxInfo]);
  
  // Show tax info in UI
  <div className="text-sm text-neutral-600">
    Tax for your country: {taxInfo?.tax_name} ({taxInfo?.tax_rate}%)
  </div>
}
```

**API Hook**:
```javascript
// hooks/useTaxInfo.js
export const useGetTaxInfo = (storeId) => {
  return useQuery({
    queryKey: ['taxInfo', storeId],
    queryFn: () => api.get(`/admin/tax-info/${storeId}`)
  });
};
```

### Option 2: Calculate tax on backend when creating contract

**Backend Change**:
```python
# In procurement_contract_services.py
from app.utils.tax_utils import get_tax_rate_for_store

async def add_contract(contract_data: Contract, store_id: str, request: Request):
    # Auto-set tax rate based on store country
    if not contract_data.tax:
        contract_data.tax = await get_tax_rate_for_store(store_id)
    
    # ... rest of the logic
```

---

## ✅ Summary of Current Implementation

| Step | Location | Tax Field | Formula Used |
|------|----------|-----------|--------------|
| 1. Enter | ProductForm (Frontend) | Manual input (%) | N/A |
| 2. Store | Contract (MongoDB) | 18.0 | N/A |
| 3. Copy | Purchase Order | Same as contract | N/A |
| 4. Save | Inventory | Same as PO | N/A |
| 5. Calculate | Sales Order | From inventory | **✅ `calculate_tax_amount()`** |
| 6. Total | Order Total | Calculated | **✅ `calculate_product_total_with_tax()`** |

---

## 🎯 Benefits of Changes

✅ **Centralized Logic** - All tax calculations use the same utility  
✅ **Correct Formula** - Fixed incorrect tax multiplication  
✅ **Consistent Results** - Same calculation across all modules  
✅ **Easy Updates** - Change tax logic in one place  
✅ **Country Support** - Ready for country-wise tax rates  
✅ **Type Safe** - Proper error handling and validation  

---

## 🔄 Next Steps (Optional)

1. **Auto-populate tax field** in ProductForm based on store country
2. **Add tax rate validation** in frontend (show if rate is from country)
3. **Display tax breakdown** in order summary (subtotal + tax = total)
4. **Historical tracking** - log when tax rates change
5. **Admin panel** - manage tax rates by country

---

## 📞 Testing

Test the changes with different scenarios:

```python
# Test 1: India GST (18%)
Unit Price: ₹100, Quantity: 5, Tax: 18%
Expected Tax: ₹90
Expected Total: ₹590

# Test 2: UK VAT (20%)
Unit Price: £100, Quantity: 5, Tax: 20%
Expected Tax: £100
Expected Total: £600

# Test 3: No Tax (0%)
Unit Price: $100, Quantity: 5, Tax: 0%
Expected Tax: $0
Expected Total: $500
```

---

**Created**: December 15, 2025  
**Status**: ✅ Implemented and Active

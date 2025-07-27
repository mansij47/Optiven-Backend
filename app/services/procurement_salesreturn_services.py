from app.db import db
from typing import List
from fastapi import  HTTPException
from app.models.procurement_models import ReturnOrderSummary
from app.models.procurement_models import ReturnOrderDetail, ProductDetails

return_orders_collection = db["ReturnOrders"]


#List of Return Order from Sales
async def get_return_orders_for_table_view(store_id: str) -> List[ReturnOrderSummary]:
    orders = await return_orders_collection.find({"store_id": store_id}).to_list(length=None)

    result = []
    for order in orders:
        product_list = order.get("product", [])
        product_name = product_list[0].get("product_name") if product_list else "N/A"

        returned_amount = order.get("returned_amount")
        if returned_amount is None:
            returned_amount = 0.0  # fallback to avoid validation error

        result.append(ReturnOrderSummary(
            order_id=order.get("order_id", "N/A"),
            return_id=order.get("return_id", "N/A"),
            product_name=product_name,
            customer_name=order.get("customer_name", "N/A"),
            returned_amount=returned_amount,
        ))

    return result


#Veiw the details of Return order
async def get_return_order_detail(return_id: str, store_id: str) -> ReturnOrderDetail:
    order = await return_orders_collection.find_one({
        "return_id": return_id,
        "store_id": store_id
    })

    if not order:
        raise HTTPException(status_code=404, detail="Return order not found")

    # Parse product list
    product_list = order.get("product", [])
    parsed_products = [ProductDetails(
        product_id=prod.get("product_id"),
        product_name=prod.get("product_name"),
        quantity=prod.get("quantity"),
        unit_price=prod.get("unit_price"),
        tax=prod.get("tax")
    ) for prod in product_list]

    return ReturnOrderDetail(
        return_id=order.get("return_id"),
        order_id=order.get("order_id"),
        customer_id=order.get("customer_id"),
        customer_name=order.get("customer_name"),
        phone_no=order.get("phone_no"),
        email=order.get("email"),
        product=parsed_products,
        return_date=order.get("return_date"),
        is_customer_returnable=order.get("is_customer_returnable"),
        remarks=order.get("remarks"),
        reason=order.get("reason"),
        returned_amount=order.get("returned_amount"),
        store_id=order.get("store_id")
    )

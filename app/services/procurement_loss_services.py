from fastapi import HTTPException
from app.models.procurement_models import LossOrder
from app.db import db  
from bson.objectid import ObjectId

#List of Loss Orders
async def get_loss_orders_by_store(store_id: str):
    cursor = db.LossOrders.find({"store_id": store_id})
    loss_orders = []

    async for order in cursor:
        order.pop("_id", None)

        quantity = order.get("quantity_lost", 0)
        price = order.get("unit_price", 0.0)

        try:
            loss = float(quantity) * float(price)
        except (ValueError, TypeError):
            loss = 0.0

        # ✅ Add `loss_amount` just for response
        order["loss_amount"] = round(loss, 2)

        loss_orders.append(order)

    if not loss_orders:
        raise HTTPException(status_code=404, detail="No loss orders found for this store.")

    return loss_orders


#Veiw loss order details by Product_id 
async def get_loss_orders_by_product_id(product_id: str, store_id: str):
    cursor = db.LossOrders.find({
        "product_id": product_id,
        "store_id": store_id
    })

    loss_orders = []

    async for order in cursor:
        order.pop("_id", None)

        quantity = order.get("quantity_lost", 0)
        price = order.get("unit_price", 0.0)

        try:
            loss = float(quantity) * float(price)
        except (ValueError, TypeError):
            loss = 0.0

        # ✅ Add `loss_amount` just for response
        order["loss_amount"] = round(loss, 2)

        loss_orders.append(order)

    if not loss_orders:
        raise HTTPException(status_code=404, detail="No loss orders found for this product in your store.")

    return loss_orders
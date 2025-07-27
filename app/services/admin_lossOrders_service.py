from fastapi import HTTPException
from app.db import db
from app.models.admin_model import LossOrder
import csv
import io
from fastapi.responses import StreamingResponse
from collections import defaultdict
from typing import List, Dict


async def export_loss_orders_csv(store_id: str, org_id: str):
    cursor = db.LossOrders.find({"store_id": store_id, "org_id": org_id})
    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV headers
    writer.writerow([
        "product_id", "org_id", "store_id", "product_name", "category",
        "date_reported", "quantity_lost", "unit", "unit_price", "reason"
    ])

    # Write data rows
    async for doc in cursor:
        writer.writerow([
            doc.get("product_id", ""),
            doc.get("org_id", ""),
            doc.get("store_id", ""),
            doc.get("product_name", ""),
            doc.get("category", ""),
            doc.get("date_reported", ""),
            doc.get("quantity_lost", ""),
            doc.get("unit", ""),
            doc.get("unit_price", ""),
            doc.get("reason", ""),
        ])

    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=loss_orders.csv"
    })


async def get_all_loss_orders_with_metrics(store_id: str, org_id: str, total_inventory_value: float = 100000.0) -> Dict:
    try:
        cursor = db.LossOrders.find({"store_id": store_id, "org_id": org_id})
        loss_orders = []
        orders_for_metrics = []

        async for doc in cursor:
            doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
            loss_orders.append(doc)

            # Prepare for metrics
            try:
                order = LossOrder(**doc)
                orders_for_metrics.append(order)
            except Exception:
                continue  # Skip invalid records

        # Compute metrics
        metrics = calculate_loss_metrics(orders_for_metrics, total_inventory_value)

        return {
            "count": len(loss_orders),
            "loss_orders": loss_orders,
            "loss_metrics": metrics
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch loss orders: {str(e)}")


def calculate_loss_metrics(orders: List[LossOrder], total_inventory_value: float = 100000.0) -> Dict:
    current_loss_entries = []
    total_loss_value = 0
    category_loss_map = defaultdict(float)

    for order in orders:
        loss_value = order.quantity_lost * order.unit_price
        total_loss_value += loss_value
        category_loss_map[order.category] += loss_value

        current_loss_entries.append({
            "product_id": order.product_id,
            "product_name": order.product_name,
            "current_loss": loss_value,
            "reason": order.reason
        })

    most_affected_category = max(category_loss_map.items(), key=lambda x: x[1])[0] if category_loss_map else None
    loss_percentage = (total_loss_value / total_inventory_value) * 100 if total_inventory_value > 0 else 0

    return {
        "current_loss_entries": current_loss_entries,
        "total_loss_value": round(total_loss_value, 2),
        "product_loss_count": len(orders),
        "most_affected_category": most_affected_category,
        "loss_percentage": round(loss_percentage, 2)
    }
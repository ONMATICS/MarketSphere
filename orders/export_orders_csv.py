import csv
import io
from decimal import Decimal
from django.utils.encoding import smart_str
from .models import Order  # Adjust the import path based on your app structure

def sanitize_csv_value(value):
    """
    Prevents CSV injection attacks (Formula Injection) by escaping
    cells that start with dangerous characters.
    """
    if value is None:
        return ""
    
    val_str = smart_str(value).strip()
    # If the string starts with a formula character, prefix it with a single quote
    if val_str and val_str[0] in ('=', '+', '-', '@'):
        return f"'{val_str}"
        
    return val_str

def generate_seller_orders_csv(seller) -> str:
    """
    Generates a CSV string containing all orders and order items for a specific seller.
    """
    output = io.StringIO()
    # Add UTF-8 Byte Order Mark (BOM) so Excel automatically recognizes the encoding
    output.write('\ufeff') 
    
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Define headers based on the required columns
    headers = [
        "Order Number", "Order Date", "Order Status", "Payment Status",
        "Buyer Name", "Buyer Email", "Buyer Phone",
        "Shipping Name", "Shipping Phone", "Shipping Address", "Shipping City", 
        "Shipping Postal Code", "Courier", "Tracking Number", 
        "Estimated Delivery Date", "Shipped At", "Delivered At",
        "Product Name", "Product SKU", "Quantity Ordered", "Unit Price", "Item Total",
        "Order Subtotal", "Shipping Cost", "Order Discount", "Tax", "Order Total",
        "Seller Notes", "Buyer Notes", "Order Updated At"
    ]
    writer.writerow(headers)

    # Query the orders, optimizing related object fetches
    orders = Order.objects.filter(
        seller=seller
    ).select_related(
        'user'
    ).prefetch_related(
        'items__product'
    ).order_by('-created_at')

    for order in orders:
        # Prepare the shared order-level data
        buyer_name = order.user.get_full_name() or order.user.username
        
        base_order_data = [
            order.order_number,
            order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
            order.get_status_display(),
            order.get_payment_status_display(),
            buyer_name,
            order.user.email,
            order.user.contact,  # From your User model
            order.shipping_name,
            order.shipping_phone,
            order.shipping_address,
            order.shipping_city,
            order.shipping_postal_code,
            order.courier,
            order.tracking_number,
            order.estimated_delivery.strftime("%Y-%m-%d") if order.estimated_delivery else "",
            order.shipped_at.strftime("%Y-%m-%d %H:%M:%S") if order.shipped_at else "",
            order.delivered_at.strftime("%Y-%m-%d %H:%M:%S") if order.delivered_at else "",
        ]

        financial_and_notes_data = [
            order.subtotal,
            order.shipping_cost,
            order.discount,
            order.tax,
            order.total,
            order.seller_notes,
            order.buyer_notes,
            order.updated_at.strftime("%Y-%m-%d %H:%M:%S") if order.updated_at else "",
        ]

        items = order.items.all()
        
        # Handle orders safely even if they have no items
        if not items:
            empty_item_data = ["", "", "", "", ""]
            row = base_order_data + empty_item_data + financial_and_notes_data
            writer.writerow([sanitize_csv_value(v) for v in row])
        else:
            for item in items:
                # We use getattr in case the Product model lacks a name/sku field 
                # (since the exact Product model wasn't provided, this prevents crashes)
                product_name = getattr(item.product, 'name', f"Product ID: {item.product_id}")
                product_sku = getattr(item.product, 'sku', "")
                
                item_data = [
                    product_name,
                    product_sku,
                    item.quantity,
                    item.price,
                    item.total
                ]
                
                row = base_order_data + item_data + financial_and_notes_data
                writer.writerow([sanitize_csv_value(v) for v in row])

    return output.getvalue()
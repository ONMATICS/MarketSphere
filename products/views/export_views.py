from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from accounts.models import Seller
from products import services
from products.models import Product
from products.product_pdf import export_product_report
from services.decorators.decorators import catalog_admin_required


@catalog_admin_required
def export_product_pdf(request: HttpRequest, slug: str) -> HttpResponse:
    """Generate a PDF report for a single product."""
    product_obj = get_object_or_404(
        Product.objects.select_related(
            "category",
            "brand",
            "seller",
        ).prefetch_related(
            "images",
            "order_items__seller_order__order",
        ),
        slug=slug,
    )

    return export_product_report(product=product_obj, admin_user=request.user)


@catalog_admin_required
def export_product_orders_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Export all orders containing a specific product."""
    product_obj = get_object_or_404(
        Product.objects.select_related("seller", "category", "brand"),
        slug=slug,
    )
    return services.export_product_orders(product_obj)


@catalog_admin_required
def export_products_csv(request: HttpRequest, seller_id: int) -> HttpResponse:
    """Export a CSV of all products for a specified seller."""
    seller = get_object_or_404(Seller, id=seller_id)
    return services.export_products_csv(seller)

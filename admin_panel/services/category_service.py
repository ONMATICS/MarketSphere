import csv
import io
import json
from datetime import timedelta
from typing import Any

from django.db.models import Count, DecimalField, QuerySet, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

from orders.models import Order, OrderItem
from products.models import Category, Product


def get_categories_data() -> dict[str, Any]:
    """Retrieve deep analytics and relational hierarchies for category models."""
    now = timezone.now()

    categories = (
        Category.objects.annotate(
            product_count=Count("products", distinct=True),
            subcategory_count=Count("children", distinct=True),
        )
        .select_related("parent")
        .prefetch_related("products")
        .order_by("name")
    )

    total_categories = categories.count()
    active_categories = categories.filter(is_active=True).count()
    category_nodes = {}

    for category in categories:
        category_products = []
        for product in category.products.all():
            sold_units = (
                product.order_items.filter(order__payment_status=Order.PaymentStatus.PAID)
                .aggregate(total=Coalesce(Sum("quantity"), 0))["total"] or 0
            )
            category_products.append({
                "id": product.id, "name": product.name, "slug": product.slug, "sku": product.sku or "",
                "seller": getattr(product.seller, "store_name", "") if product.seller else "",
                "price": str(product.discount_price or product.price or ""), "stock_quantity": product.stock_quantity,
                "status": product.status, "orders": sold_units,
            })

        paid_order_items = OrderItem.objects.filter(product__category=category, order__payment_status=Order.PaymentStatus.PAID)
        order_summary = paid_order_items.aggregate(
            order_count=Count("order", distinct=True),
            revenue=Coalesce(Sum("total"), 0, output_field=DecimalField(max_digits=18, decimal_places=2))
        )
        
        top_products = sorted([p for p in category_products if p["orders"]], key=lambda p: p["orders"], reverse=True)[:4]
        
        revenue_trend, growth_trend = [], []
        for month_offset in range(8, -1, -1):
            month_index = now.year * 12 + now.month - 1 - month_offset
            month_start = now.replace(year=month_index // 12, month=month_index % 12 + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (month_start + timedelta(days=32)).replace(day=1)
            month_summary = paid_order_items.filter(order__created_at__gte=month_start, order__created_at__lt=next_month).aggregate(
                order_count=Count("order", distinct=True),
                revenue=Coalesce(Sum("total"), 0, output_field=DecimalField(max_digits=18, decimal_places=2))
            )
            revenue_trend.append({"label": month_start.strftime("%b"), "value": str(month_summary["revenue"] or 0)})
            growth_trend.append({"label": month_start.strftime("%b"), "value": month_summary["order_count"] or 0})

        category_nodes[category.id] = {
            "id": category.id, "name": category.name, "slug": category.slug,
            "description": category.description or "", "icon": category.icon or "bi bi-grid",
            "image": category.image if category.image else "",
            "is_active": category.is_active, "status": "active" if category.is_active else "inactive",
            "parent_id": category.parent_id, "_parentName": category.parent.name if category.parent else None,
            "parent": {"id": category.parent.id, "name": category.parent.name, "slug": category.parent.slug} if category.parent else None,
            "product_count": category.product_count, "products": category_products, "subcategory_count": category.subcategory_count,
            "children": [],
            "analytics": {
                "published": category.products.filter(status=Product.Status.PUBLISHED).count(),
                "pending": category.products.filter(status=Product.Status.PENDING).count(),
                "out_of_stock": category.products.filter(status=Product.Status.OUT_OF_STOCK).count(),
                "orders": order_summary["order_count"] or 0, "revenue": str(order_summary["revenue"] or 0),
                "conversion_rate": None, "top_products": top_products, "revenue_trend": revenue_trend, "growth_trend": growth_trend,
            },
            "created_at": category.created_at.isoformat() if getattr(category, "created_at", None) else None,
            "updated_at": category.updated_at.isoformat() if getattr(category, "updated_at", None) else None,
            "created": category.created_at.strftime("%b %d, %Y") if getattr(category, "created_at", None) else None,
            "updated": category.updated_at.strftime("%b %d, %Y") if getattr(category, "updated_at", None) else None,
        }

    category_tree = []
    for category in categories:
        node = category_nodes[category.id]
        if category.parent_id is None: category_tree.append(node)
        else:
            parent_node = category_nodes.get(category.parent_id)
            if parent_node: parent_node["children"].append(node)

    return {
        "categories": list(category_nodes.values()),
        "category_tree": category_tree,
        "total_categories": total_categories,
        "active_categories": active_categories,
        "inactive_categories": categories.filter(is_active=False).count(),
        "percentage_active": round((active_categories / total_categories) * 100, 1) if total_categories else 0,
        "categories_added_this_month": categories.filter(created_at__year=now.year, created_at__month=now.month).count(),
        "total_parent_categories": categories.filter(parent__isnull=True).count(),
        "total_subcategories": categories.filter(parent__isnull=False).count(),
        "empty_categories": categories.filter(product_count=0).count(),
        "products_assigned": Product.objects.filter(category__isnull=False).count(),
        "average_products_per_category": round((Product.objects.filter(category__isnull=False).count() / total_categories), 1) if total_categories else 0,
    }


def get_categories_api_data() -> dict[str, Any]:
    """Return JSON-safe category data specifically tailored for frontend apps."""
    context = get_categories_data()
    return {
        "categories": context["category_tree"],
        "category_tree": context["category_tree"],
        "total_categories": context["total_categories"],
        "active_categories": context["active_categories"],
        "inactive_categories": context["inactive_categories"],
        "percentage_active": context["percentage_active"],
        "categories_added_this_month": context["categories_added_this_month"],
        "total_parent_categories": context["total_parent_categories"],
        "total_subcategories": context["total_subcategories"],
        "empty_categories": context["empty_categories"],
        "products_assigned": context["products_assigned"],
        "average_products_per_category": context["average_products_per_category"],
    }


def export_categories(export_format: str = "CSV", category_ids: list[int] | None = None) -> HttpResponse:
    """Entry point for exporting category models into varying formats."""
    export_format = str(export_format or "CSV").upper()
    categories = Category.objects.select_related("parent").annotate(
        product_count=Count("products", distinct=True),
        subcategory_count=Count("children", distinct=True),
    ).order_by("name")

    if category_ids:
        categories = categories.filter(id__in=category_ids)

    if export_format == "CSV": return _export_categories_csv(categories)
    if export_format == "JSON": return _export_categories_json(categories)
    if export_format == "PDF": return _export_categories_pdf(categories)
    raise ValueError("Unsupported export format.")


def _export_categories_csv(categories: QuerySet[Category]) -> HttpResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Slug", "Parent", "Type", "Status", "Products", "Subcategories", "Description", "Icon", "Image"])

    for category in categories:
        writer.writerow([
            category.id, category.name, category.slug, category.parent.name if category.parent else "",
            "Subcategory" if category.parent_id else "Category", "Active" if category.is_active else "Inactive",
            category.product_count, category.subcategory_count, category.description or "", category.icon or "",
            category.image if category.image else "",
        ])

    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="categories.csv"'
    return response


def _export_categories_json(categories: QuerySet[Category]) -> HttpResponse:
    data = [{
        "id": category.id, "name": category.name, "slug": category.slug,
        "parent_id": category.parent_id, "parent": {"id": category.parent.id, "name": category.parent.name, "slug": category.parent.slug} if category.parent else None,
        "type": "Subcategory" if category.parent_id else "Category",
        "status": "active" if category.is_active else "inactive", "is_active": category.is_active,
        "product_count": category.product_count, "subcategory_count": category.subcategory_count,
        "description": category.description or "", "icon": category.icon or "",
        "image": category.image if category.image else "",
        "created_at": category.created_at.isoformat() if getattr(category, "created_at", None) else None,
        "updated_at": category.updated_at.isoformat() if getattr(category, "updated_at", None) else None,
    } for category in categories]

    response = HttpResponse(json.dumps(data, indent=2, ensure_ascii=False), content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="categories.json"'
    return response


ACCENT_COLOR = colors.HexColor("#9D6638")
HEADING_COLOR = colors.HexColor("#4E220F")
MUTED_COLOR = colors.HexColor("#6B6B6B")
BORDER_COLOR = colors.HexColor("#D9D2C4")
LIGHT_BG = colors.HexColor("#F7F1DE")
PAGE_MARGIN = 20 * mm


def _get_styles() -> Any:
    """Defines the typography system for the PDF report."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportBrand", fontName="Helvetica-Bold", fontSize=20, textColor=HEADING_COLOR, spaceAfter=4))
    styles.add(ParagraphStyle(name="ReportTitle", fontName="Helvetica", fontSize=12, spaceBefore=4, textColor=MUTED_COLOR))
    styles.add(ParagraphStyle(name="MetaRight", fontName="Helvetica", fontSize=9, textColor=MUTED_COLOR, alignment=TA_RIGHT, leading=12))
    styles.add(ParagraphStyle(name="TableHeader", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="TableCell", fontName="Helvetica", fontSize=9, textColor=colors.black, leading=12, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="TableCellLeft", parent=styles["TableCell"], alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="TableCellRight", parent=styles["TableCell"], alignment=TA_RIGHT))
    return styles


def _draw_footer(canvas: Any, doc: Any) -> None:
    """Canvas hook for drawing the universal footer on every PDF page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED_COLOR)
    timestamp = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
    landscape_width = landscape(A4)[0]
    canvas.drawString(PAGE_MARGIN, 10 * mm, f"MarketSphere Admin Dashboard | {timestamp}")
    canvas.drawCentredString(landscape_width / 2.0, 10 * mm, "Confidential Document")
    canvas.drawRightString(landscape_width - PAGE_MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _build_data_table(
    headers: list[str], row_data: list[list[str]], col_widths: list[float], styles: Any,
    align_left_cols: list[int] | None = None, align_right_cols: list[int] | None = None
) -> Table:
    """Builds standard list tables for PDF generation with alternating row colors."""
    align_left_cols = align_left_cols or []
    align_right_cols = align_right_cols or []
    table_data = [[Paragraph(h, styles["TableHeader"]) for h in headers]]

    if not row_data:
        table_data.append([Paragraph("<i>No data available</i>", styles["TableCellLeft"])] + [""] * (len(headers) - 1))
    else:
        for row in row_data:
            formatted_row = []
            for idx, cell_value in enumerate(row):
                style = styles["TableCellLeft"] if idx in align_left_cols else (styles["TableCellRight"] if idx in align_right_cols else styles["TableCell"])
                formatted_row.append(Paragraph(str(cell_value), style))
            table_data.append(formatted_row)

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADING_COLOR), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR), ('INNERGRID', (0, 0), (-1, -1), 0.25, BORDER_COLOR),
    ]
    if row_data:
        t_style.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_BG]))
    t.setStyle(TableStyle(t_style))
    return t


def _export_categories_pdf(categories: QuerySet[Category]) -> HttpResponse:
    buffer = io.BytesIO()
    styles = _get_styles()

    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN, bottomMargin=PAGE_MARGIN, title="MarketSphere - Category Export"
    )

    brand_block = [Paragraph("MARKETSPHERE", styles["ReportBrand"]), Paragraph("Category Export Report", styles["ReportTitle"])]
    meta_block = [
        Paragraph(f"<b>Generated Date:</b> {timezone.now().strftime('%b %d, %Y')}", styles["MetaRight"]),
        Paragraph(f"<b>Time:</b> {timezone.now().strftime('%H:%M:%S')}", styles["MetaRight"]),
        Paragraph(f"<b>Total Categories:</b> {len(categories)}", styles["MetaRight"]),
    ]
    
    header_table = Table([[brand_block, meta_block]], colWidths=[130*mm, 127*mm])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    
    elements = [header_table, Spacer(1, 10), HRFlowable(width="100%", thickness=1.5, color=ACCENT_COLOR, spaceAfter=15)]
    headers = ["ID", "Category", "Slug", "Parent", "Type", "Status", "Products", "Subcategories"]
    row_data = [[str(c.id), c.name, c.slug, c.parent.name if c.parent else "Top Level", "Subcategory" if c.parent_id else "Category", "Active" if c.is_active else "Inactive", str(c.product_count), str(c.subcategory_count)] for c in categories]
    col_widths = [15*mm, 45*mm, 45*mm, 45*mm, 25*mm, 22*mm, 25*mm, 35*mm]

    elements.append(_build_data_table(headers, row_data, col_widths, styles, align_left_cols=[1, 2, 3], align_right_cols=[6, 7]))
    document.build(elements, onFirstPage=_draw_footer, onLaterPages=_draw_footer)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="categories.pdf"'
    return response
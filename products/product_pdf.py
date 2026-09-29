"""
services/product_pdf.py

Dedicated ReportLab service for generating MarketSphere Product Reports.
Follows the exact design system and structure of seller_pdf.py and buyer_pdf.py.
"""
import os
from io import BytesIO
import datetime
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Sum, Count, Q, F

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether, Image as RLImage
)


# =============================================================
# BRAND & STYLE CONSTANTS (Imported/Matched from existing PDFs)
# =============================================================
ACCENT_COLOR = colors.HexColor("#9D6638")
HEADING_COLOR = colors.HexColor("#4E220F")
MUTED_COLOR = colors.HexColor("#6B6B6B")
BORDER_COLOR = colors.HexColor("#D9D2C4")
LIGHT_BG = colors.HexColor("#F7F1DE")

PAGE_MARGIN = 20 * mm


def _get_styles():
    """Defines the typography system for the report."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportBrand", fontName="Helvetica-Bold", fontSize=20, textColor=HEADING_COLOR, spaceAfter=4))
    styles.add(ParagraphStyle(name="ReportTitle", fontName="Helvetica", fontSize=12, spaceBefore=4, textColor=MUTED_COLOR))
    styles.add(ParagraphStyle(name="MetaRight", fontName="Helvetica", fontSize=9, textColor=MUTED_COLOR, alignment=TA_RIGHT, leading=12))
    styles.add(ParagraphStyle(name="SectionHeading", fontName="Helvetica-Bold", fontSize=12, textColor=HEADING_COLOR, spaceBefore=15, spaceAfter=6))
    styles.add(ParagraphStyle(name="KeyStyle", fontName="Helvetica-Bold", fontSize=9, textColor=HEADING_COLOR))
    styles.add(ParagraphStyle(name="ValueStyle", fontName="Helvetica", fontSize=9, textColor=colors.black))
    styles.add(ParagraphStyle(name="NotesBody", fontName="Helvetica", fontSize=9, textColor=colors.black, leading=14))
    styles.add(ParagraphStyle(name="TableHeader", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="TableCell", fontName="Helvetica", fontSize=9, textColor=colors.black, leading=12, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="TableCellLeft", parent=styles["TableCell"], alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="TableCellRight", parent=styles["TableCell"], alignment=TA_RIGHT))
    return styles

def _format_currency(value):
    try:
        return f"Rs. {float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "Rs. 0.00"

def _yes_no(value):
    return "Yes" if value else "No"

def _safe_str(value, default="—"):
    if value is None or str(value).strip() == "":
        return default
    return str(value)

def _get_safe_image(image_field, max_width=40*mm, max_height=40*mm):
    """Safely attempts to load a Django ImageField into a ReportLab Image."""
    try:
        if image_field and bool(image_field):
            # Try local path first to avoid network latency
            if hasattr(image_field, 'path') and os.path.exists(image_field.path):
                img = RLImage(image_field.path)
            else:
                img = RLImage(image_field if isinstance(image_field, str) else image_field.url)
            
            # Maintain aspect ratio
            aspect = img.imageWidth / float(img.imageHeight)
            if aspect > 1:
                img.drawWidth = max_width
                img.drawHeight = max_width / aspect
            else:
                img.drawHeight = max_height
                img.drawWidth = max_height * aspect
            return img
    except Exception:
        pass
    
    # Fallback to a styled placeholder
    styles = _get_styles()
    return Paragraph("<font color='#999999'><i>No Image<br/>Available</i></font>", styles["TableCell"])

def _draw_footer(canvas, doc):
    """Universal footer hook."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED_COLOR)
    timestamp = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
    canvas.drawString(PAGE_MARGIN, 10 * mm, f"MarketSphere Admin Dashboard | {timestamp}")
    canvas.drawCentredString(A4[0] / 2.0, 10 * mm, "Confidential Document")
    canvas.drawRightString(A4[0] - PAGE_MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()

def _build_kv_table(data_list, styles, col_widths=None):
    """Builds the standard Key-Value grid."""
    if col_widths is None:
        col_widths = [35*mm, 50*mm, 35*mm, 50*mm]
    rows = []
    for i in range(0, len(data_list), 2):
        row = []
        item1 = data_list[i]
        row.extend([Paragraph(item1[0], styles["KeyStyle"]), Paragraph(str(item1[1]), styles["ValueStyle"])])
        if i + 1 < len(data_list):
            item2 = data_list[i+1]
            row.extend([Paragraph(item2[0], styles["KeyStyle"]), Paragraph(str(item2[1]), styles["ValueStyle"])])
        else:
            row.extend([Paragraph("", styles["KeyStyle"]), Paragraph("", styles["ValueStyle"])])
        rows.append(row)
    table = Table(rows, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    return table

def _build_data_table(headers, row_data, col_widths, styles, align_left_cols=None, align_right_cols=None):
    """Builds standard list tables with alternating row colors."""
    align_left_cols = align_left_cols or []
    align_right_cols = align_right_cols or []
    table_data = []
    
    header_row = [Paragraph(h, styles["TableHeader"]) for h in headers]
    table_data.append(header_row)
    
    if not row_data:
        table_data.append([Paragraph("<i>No data available</i>", styles["TableCellLeft"])] + [""] * (len(headers) - 1))
    else:
        for row in row_data:
            formatted_row = []
            for idx, cell_value in enumerate(row):
                style = styles["TableCellLeft"] if idx in align_left_cols else (styles["TableCellRight"] if idx in align_right_cols else styles["TableCell"])
                formatted_row.append(Paragraph(str(cell_value), style) if not isinstance(cell_value, RLImage) else cell_value)
            table_data.append(formatted_row)
            
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADING_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, BORDER_COLOR),
    ]
    if row_data:
        t_style.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_BG]))
    t.setStyle(TableStyle(t_style))
    return t


# =============================================================
# MAIN ORCHESTRATION FUNCTION
# =============================================================
def export_product_report(product, admin_user=None):
    buffer = BytesIO()
    styles = _get_styles()
    
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN, bottomMargin=PAGE_MARGIN,
        title=f"Product Report - {product.name}"
    )
    
    elements = []
    
    # --- HEADER ---
    brand_block = [
        Paragraph("MARKETSPHERE", styles["ReportBrand"]),
        Paragraph("Product Report", styles["ReportTitle"]),
    ]
    meta_block = [
        Paragraph(f"<b>Generated Date:</b> {timezone.now().strftime('%b %d, %Y')}", styles["MetaRight"]),
        Paragraph(f"<b>Time:</b> {timezone.now().strftime('%H:%M:%S')}", styles["MetaRight"]),
        Paragraph(f"<b>Admin:</b> {_safe_str(admin_user.get_full_name() if admin_user else 'System')}", styles["MetaRight"]),
        Paragraph(f"<b>Product ID:</b> {_safe_str(product.slug)}", styles["MetaRight"]),
    ]
    
    header_table = Table([[brand_block, meta_block]], colWidths=[100*mm, 70*mm])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    elements.extend([header_table, Spacer(1, 10), HRFlowable(width="100%", thickness=1.5, color=ACCENT_COLOR, spaceAfter=15)])

    # --- PRIMARY IMAGE & QUICK SUMMARY ---
    primary_image_obj = getattr(product, 'primary_image', None)
    if not primary_image_obj:
        primary_image_obj = product.images.first()
    img_element = _get_safe_image(primary_image_obj.image if primary_image_obj else None, 45*mm, 45*mm)

    summary_block = [
        Paragraph(f"<b>{product.name}</b>", ParagraphStyle('ProdTitle', parent=styles['ReportBrand'], fontSize=16)),
        Spacer(1, 4),
        Paragraph(f"<b>SKU:</b> {_safe_str(product.sku)}", styles["ValueStyle"]),
        Paragraph(f"<b>Barcode:</b> {_safe_str(product.barcode)}", styles["ValueStyle"]),
        Paragraph(f"<b>Status:</b> {_safe_str(product.status).title()}", styles["ValueStyle"]),
        Paragraph(f"<b>Created:</b> {product.created_at.strftime('%b %d, %Y')} | <b>Updated:</b> {product.updated_at.strftime('%b %d, %Y')}", styles["ValueStyle"]),
    ]
    
    top_table = Table([[img_element, summary_block]], colWidths=[55*mm, 115*mm])
    top_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.extend([top_table, Spacer(1, 15)])

    # --- CATEGORY, BRAND & SELLER ---
    cat_name = getattr(product.category, 'name', '—') if getattr(product, 'category', None) else '—'
    brand_name = getattr(product.brand, 'name', '—') if getattr(product, 'brand', None) else '—'
    seller_name = getattr(product.seller, 'store_name', '—') if getattr(product, 'seller', None) else '—'
    seller_status = getattr(product.seller, 'status', '—').title() if getattr(product, 'seller', None) else '—'

    elements.append(KeepTogether([
        Paragraph("RELATIONSHIPS", styles["SectionHeading"]),
        _build_kv_table([
            ("Category", cat_name), ("Brand", brand_name),
            ("Seller / Store", seller_name), ("Seller Status", seller_status),
        ], styles)
    ]))
    elements.append(Spacer(1, 10))

    # --- PRICING & INVENTORY ---
    discount_val = getattr(product, 'discount_percentage', None)
    discount_str = f"{discount_val}% Off" if discount_val else "—"

    elements.append(KeepTogether([
        Paragraph("PRICING & INVENTORY", styles["SectionHeading"]),
        _build_kv_table([
            ("Regular Price", _format_currency(product.price)), ("Stock Quantity", _safe_str(product.stock_quantity)),
            ("Discount Price", _format_currency(product.discount_price)), ("Minimum Stock Level", _safe_str(product.min_stock_level)),
            ("Discount Percentage", discount_str), ("Weight", _safe_str(product.weight)),
        ], styles)
    ]))
    elements.append(Spacer(1, 10))

    # --- DESCRIPTION ---
    short_desc = _safe_str(getattr(product, 'short_description', '—'))
    full_desc = _safe_str(getattr(product, 'description', '—'))
    elements.append(KeepTogether([
        Paragraph("DESCRIPTION", styles["SectionHeading"]),
        Paragraph("<b>Short Description:</b>", styles["KeyStyle"]),
        Spacer(1, 3),
        Paragraph(short_desc.replace('\n', '<br/>'), styles["NotesBody"]),
        Spacer(1, 6),
        Paragraph("<b>Full Description:</b>", styles["KeyStyle"]),
        Spacer(1, 3),
        Paragraph(full_desc.replace('\n', '<br/>'), styles["NotesBody"])
    ]))
    elements.append(Spacer(1, 10))

    # --- SALES & ORDER METRICS ---
    order_items = product.order_items.select_related('seller_order', 'seller_order__order')
    
    total_units_sold = 0
    total_revenue = 0.0
    status_counts = {"pending": 0, "confirmed": 0, "processing": 0, "shipped": 0, "delivered": 0, "cancelled": 0}
    
    orders_table_data = []

    for item in order_items:
        so = item.seller_order
        if so:
            so_status = str(so.status).lower()
            if so_status in status_counts:
                status_counts[so_status] += 1
            
            # Count revenue and units only if not cancelled
            if so_status != 'cancelled':
                total_units_sold += item.quantity
                total_revenue += float(item.total)

            # Build order history table rows
            parent_order = so.order
            order_no = getattr(parent_order, 'order_number', f"#{parent_order.id}" if parent_order else '—')
            buyer = getattr(parent_order, 'shipping_name', '—')
            pay_status = getattr(parent_order, 'payment_status', '—').title()
            
            orders_table_data.append((
                _safe_str(order_no),
                _safe_str(buyer),
                str(item.quantity),
                _format_currency(item.price),
                _format_currency(item.total),
                pay_status,
                so_status.title(),
                item.created_at.strftime("%b %d, %Y") if item.created_at else "—"
            ))

    elements.append(KeepTogether([
        Paragraph("SALES SUMMARY", styles["SectionHeading"]),
        _build_kv_table([
            ("Total Units Sold", str(total_units_sold)), ("Pending Orders", str(status_counts["pending"])),
            ("Gross Revenue", _format_currency(total_revenue)), ("Confirmed Orders", str(status_counts["confirmed"])),
            ("Processing Orders", str(status_counts["processing"])), ("Shipped Orders", str(status_counts["shipped"])),
            ("Delivered Orders", str(status_counts["delivered"])), ("Cancelled Orders", str(status_counts["cancelled"])),
        ], styles)
    ]))
    elements.append(Spacer(1, 10))

    # --- ORDER HISTORY TABLE ---
    elements.append(KeepTogether([
        Paragraph("RECENT ORDERS", styles["SectionHeading"]),
        _build_data_table(
            headers=["Order No.", "Buyer", "Qty", "Price", "Total", "Payment", "Status", "Date"],
            row_data=orders_table_data,
            col_widths=[25*mm, 35*mm, 10*mm, 20*mm, 25*mm, 20*mm, 20*mm, 15*mm],
            styles=styles,
            align_left_cols=[0, 1],
            align_right_cols=[3, 4]
        )
    ]))
    elements.append(Spacer(1, 10))

    # --- PRODUCT MODERATION ---
    elements.append(KeepTogether([
        Paragraph("PRODUCT MODERATION", styles["SectionHeading"]),
        _build_kv_table([
            ("Approved", _yes_no(getattr(product, 'is_approved', False))),
            ("Featured", _yes_no(getattr(product, 'is_featured', False))),
        ], styles),
        Spacer(1, 6),
        Paragraph("<b>Admin Notes:</b>", styles["KeyStyle"]),
        Spacer(1, 3),
        Paragraph(_safe_str(getattr(product, 'admin_notes', '—')).replace('\n', '<br/>'), styles["NotesBody"])
    ]))

    # Build PDF
    doc.build(elements, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    
    buffer.seek(0)
    date_str = timezone.now().strftime("%Y-%m-%d")
    filename = f"product-report-{product.slug}-{date_str}.pdf"

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

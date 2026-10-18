from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from orders import services as order_service
from orders.models import Order


@staff_member_required
def sales_orders(request: HttpRequest) -> HttpResponse:
    orders = order_service.get_admin_orders()
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    query_params = request.GET.copy()
    query_params.pop("page", None)
    admin_stats = order_service.get_admin_order_stats()

    return render(request, "sales/orders/order_list.html", {
        "dashboard_orders": page_obj,
        "admin": admin_stats,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })

@staff_member_required
def sales_order(request: HttpRequest, order_number: str) -> HttpResponse:
    order = Order.objects.filter(order_number=order_number).first()
    return render(request, "sales/orders/order_detail.html", {'order': order})

@staff_member_required
def payment_management(request: HttpRequest) -> HttpResponse:
    return render(request, "sales/payments/payment_management.html")
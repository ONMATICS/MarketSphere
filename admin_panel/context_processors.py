from calendar import month_abbr
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate, TruncHour, TruncMonth
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone

from accounts.models import Seller, User
from notifications.models import ActivityLog
from orders.models import Order
from products.models import Category, Product


def _calculate_change(current, previous, is_decimal=False):
    """Helper to calculate percentage change between current and previous values."""
    if previous > 0:
        return ((current - previous) / previous) * 100
    if is_decimal:
        return Decimal("100.00") if current > 0 else Decimal("0.00")
    return 100 if current > 0 else 0

def get_sales_chart_data():
    """
    Prepare marketplace revenue data for Today, 7 Days, 30 Days,
    and 12 Months.

    Revenue is calculated from paid orders using Order.created_at.
    All periods include zero-revenue intervals.
    """

    now = timezone.localtime(timezone.now())
    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    paid_orders = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID,
    )

    # ------------------------------------------
    # TODAY: Hourly revenue
    # ------------------------------------------
    hourly_start = today_start

    hourly_revenue = (
        paid_orders.filter(
            created_at__gte=hourly_start,
            created_at__lte=now,
        )
        .annotate(bucket=TruncHour("created_at"))
        .values("bucket")
        .annotate(revenue=Sum("total"))
        .order_by("bucket")
    )

    hourly_lookup = {
        row["bucket"].replace(
            minute=0,
            second=0,
            microsecond=0,
        ): row["revenue"] or Decimal("0.00")
        for row in hourly_revenue
    }

    today_data = []

    for hour in range(24):
        bucket = today_start + timedelta(hours=hour)

        # Do not display future hours as if they have occurred.
        if bucket > now:
            break

        today_data.append({
            "label": bucket.strftime("%I %p").lstrip("0"),
            "revenue": float(
                hourly_lookup.get(bucket, Decimal("0.00"))
            ),
        })

    # ------------------------------------------
    # 7 DAYS: Daily revenue
    # ------------------------------------------
    seven_days_start = today_start - timedelta(days=6)

    seven_day_revenue = (
        paid_orders.filter(
            created_at__gte=seven_days_start,
            created_at__lte=now,
        )
        .annotate(bucket=TruncDate("created_at"))
        .values("bucket")
        .annotate(revenue=Sum("total"))
        .order_by("bucket")
    )

    seven_day_lookup = {
        row["bucket"]: row["revenue"] or Decimal("0.00")
        for row in seven_day_revenue
    }

    seven_days_data = []

    for offset in range(7):
        day = seven_days_start.date() + timedelta(days=offset)

        seven_days_data.append({
            "label": day.strftime("%a"),
            "revenue": float(
                seven_day_lookup.get(day, Decimal("0.00"))
            ),
        })

    # ------------------------------------------
    # 30 DAYS: Daily revenue
    # ------------------------------------------
    thirty_days_start = today_start - timedelta(days=29)

    thirty_day_revenue = (
        paid_orders.filter(
            created_at__gte=thirty_days_start,
            created_at__lte=now,
        )
        .annotate(bucket=TruncDate("created_at"))
        .values("bucket")
        .annotate(revenue=Sum("total"))
        .order_by("bucket")
    )

    thirty_day_lookup = {
        row["bucket"]: row["revenue"] or Decimal("0.00")
        for row in thirty_day_revenue
    }

    thirty_days_data = []

    for offset in range(30):
        day = thirty_days_start.date() + timedelta(days=offset)

        thirty_days_data.append({
            "label": day.strftime("%d %b"),
            "revenue": float(
                thirty_day_lookup.get(day, Decimal("0.00"))
            ),
        })

    # ------------------------------------------
    # 12 MONTHS: Monthly revenue
    # ------------------------------------------
    current_month_start = today_start.replace(day=1)

    twelve_months_start = current_month_start

    for _ in range(11):
        if twelve_months_start.month == 1:
            twelve_months_start = twelve_months_start.replace(
                year=twelve_months_start.year - 1,
                month=12,
            )
        else:
            twelve_months_start = twelve_months_start.replace(
                month=twelve_months_start.month - 1,
            )

    monthly_revenue = (
        paid_orders.filter(
            created_at__gte=twelve_months_start,
            created_at__lte=now,
        )
        .annotate(bucket=TruncMonth("created_at"))
        .values("bucket")
        .annotate(revenue=Sum("total"))
        .order_by("bucket")
    )

    monthly_lookup = {
        row["bucket"].replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ): row["revenue"] or Decimal("0.00")
        for row in monthly_revenue
    }

    twelve_months_data = []

    month_cursor = twelve_months_start

    for _ in range(12):
        twelve_months_data.append({
            "label": month_cursor.strftime("%b"),
            "revenue": float(
                monthly_lookup.get(
                    month_cursor,
                    Decimal("0.00"),
                )
            ),
        })

        if month_cursor.month == 12:
            month_cursor = month_cursor.replace(
                year=month_cursor.year + 1,
                month=1,
            )
        else:
            month_cursor = month_cursor.replace(
                month=month_cursor.month + 1,
            )

    # ------------------------------------------
    # Return all chart datasets
    # ------------------------------------------
    return {
        "today": today_data,
        "7d": seven_days_data,
        "30d": thirty_days_data,
        "12m": twelve_months_data,
    }

def admin_context(request):
    # ==========================================
    # 1. DATE & TIME BOUNDARIES
    # ==========================================
    today = timezone.now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    thirty_days_ago = today - timedelta(days=30)
    sixty_days_ago = today - timedelta(days=60)
    ninety_days_ago = today - timedelta(days=90)

    current_month_start = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    if current_month_start.month == 1:
        previous_month_start = current_month_start.replace(
            year=current_month_start.year - 1, month=12
        )
    else:
        previous_month_start = current_month_start.replace(
            month=current_month_start.month - 1
        )

    # ==========================================
    # 2. REVENUE & SALES
    # ==========================================
    total_revenue = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID
    ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    current_month_revenue = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID,
        created_at__gte=current_month_start,
    ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    previous_month_revenue = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID,
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    percentage_change = _calculate_change(
        current_month_revenue, previous_month_revenue, is_decimal=True
    )

    today_sales = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID,
        created_at__gte=today_start,
    ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    yesterday_sales = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID,
        created_at__gte=yesterday_start,
        created_at__lt=today_start,
    ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    sales_change = _calculate_change(today_sales, yesterday_sales)

    # ==========================================
    # 3. ORDERS
    # ==========================================
    current_month_orders = Order.objects.filter(
        created_at__gte=current_month_start
    ).count()
    previous_month_orders = Order.objects.filter(
        created_at__gte=previous_month_start, created_at__lt=current_month_start
    ).count()

    orders_change = _calculate_change(current_month_orders, previous_month_orders)
    
    latest_orders = (
        Order.objects.select_related("user", "seller")
        .order_by("-created_at")[:5]
    )

    # ==========================================
    # 4. PRODUCTS & CATEGORIES
    # ==========================================
    total_products = Product.objects.exclude(
        status__in=[Product.Status.PENDING, Product.Status.DRAFT]
    ).count()

    current_month_products = Product.objects.filter(
        created_at__gte=current_month_start
    ).count()
    previous_month_products = Product.objects.filter(
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    ).count()

    products_change = _calculate_change(current_month_products, previous_month_products)

    pending_products = Product.objects.filter(status=Product.Status.PENDING).count()
    low_stock_products = Product.objects.filter(
        stock_quantity__lte=get_catalog_settings().low_stock_threshold
    ).count()

    # Optimized Category Ranking: Only counts DELIVERED orders
    top_selling_categories = (
        Category.objects.filter(is_active=True)
        .annotate(
            sold=Sum(
                "products__order_items__quantity",
                filter=Q(products__order_items__order__status=Order.Status.DELIVERED)
            )
        )
        .order_by("-sold")[:5]
    )

    # Sanitize 'sold' data (handle Nones from Sum)
    for category in top_selling_categories:
        category.sold = category.sold or 0

    max_sold = max((cat.sold for cat in top_selling_categories), default=1)
    if max_sold == 0:
        max_sold = 1

    for category in top_selling_categories:
        category.progress = round((category.sold / max_sold) * 100)

    # ==========================================
    # 5. SELLERS & VERIFICATION
    # ==========================================
    total_sellers = Seller.objects.count()
    current_month_sellers = Seller.objects.filter(
        created_at__gte=current_month_start
    ).count()
    previous_month_sellers = Seller.objects.filter(
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    ).count()

    sellers_change = _calculate_change(current_month_sellers, previous_month_sellers)

    total_verified_sellers = Seller.objects.filter(
        status=Seller.Status.VERIFIED
    ).count()
    current_month_verified_sellers = Seller.objects.filter(
        created_at__gte=current_month_start, status=Seller.Status.VERIFIED
    ).count()
    previous_month_verified_sellers = Seller.objects.filter(
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
        status=Seller.Status.VERIFIED,
    ).count()

    verified_sellers_change = _calculate_change(
        current_month_verified_sellers, previous_month_verified_sellers
    )

    active_percentage = (
        round((total_verified_sellers / total_sellers) * 100)
        if total_sellers > 0
        else 0
    )
    seller_progress = active_percentage

    if active_percentage >= 90:
        seller_health_status = "Healthy"
        seller_health_color = "healthy"
    elif active_percentage >= 75:
        seller_health_status = "Needs Review"
        seller_health_color = "attention"
    else:
        seller_health_status = "Critical"
        seller_health_color = "critical"

    # =====================================================
    # Pending Sellers
    # =====================================================
    pending_sellers = Seller.objects.filter(
        status=Seller.Status.PENDING
    ).count()

    current_month_pending = Seller.objects.filter(
        status=Seller.Status.PENDING,
        created_at__gte=current_month_start,
    ).count()

    previous_month_pending = Seller.objects.filter(
        status=Seller.Status.PENDING,
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    ).count()

    if previous_month_pending > 0:
        pending_sellers_change = round(
            ((current_month_pending - previous_month_pending) / previous_month_pending) * 100,
            1,
        )
    else:
        pending_sellers_change = 100 if current_month_pending > 0 else 0

    pending_sellers_increased = current_month_pending >= previous_month_pending

    # =====================================================
    # Suspended Sellers
    # =====================================================
    suspended_sellers = Seller.objects.filter(
        status=Seller.Status.SUSPENDED
    ).count()

    current_month_suspended = Seller.objects.filter(
        status=Seller.Status.SUSPENDED,
        created_at__gte=current_month_start,
    ).count()

    previous_month_suspended = Seller.objects.filter(
        status=Seller.Status.SUSPENDED,
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    ).count()

    if previous_month_suspended > 0:
        suspended_sellers_change = round(
            ((current_month_suspended - previous_month_suspended) / previous_month_suspended) * 100,
            1,
        )
    else:
        suspended_sellers_change = 100 if current_month_suspended > 0 else 0

    suspended_sellers_increased = current_month_suspended >= previous_month_suspended

    reviewed_today = (
        Seller.objects.filter(created_at__gte=today_start)
        .exclude(status=Seller.Status.PENDING)
        .count()
    )

    reviewed_percentage = (
        round((reviewed_today / pending_sellers) * 100) if pending_sellers > 0 else 0
    )

    if pending_sellers >= 50:
        seller_application_status = "Needs Attention"
        seller_application_color = "critical"
    elif pending_sellers >= 20:
        seller_application_status = "Moderate Queue"
        seller_application_color = "attention"
    else:
        seller_application_status = "Under Control"
        seller_application_color = "healthy"

    approved_applications = Seller.objects.filter(status=Seller.Status.VERIFIED).count()
    reviewed_applications = Seller.objects.filter(
        status__in=[Seller.Status.VERIFIED, Seller.Status.REJECTED]
    ).count()

    if reviewed_applications > 0:
        seller_approval_rate = round(
            (approved_applications / reviewed_applications) * 100, 1
        )
    else:
        seller_approval_rate = 0

    seller_approval_bars = [
        max(15, round(seller_approval_rate * 0.40)),
        max(15, round(seller_approval_rate * 0.55)),
        max(15, round(seller_approval_rate * 0.48)),
        max(15, round(seller_approval_rate * 0.70)),
        max(15, round(seller_approval_rate * 0.62)),
        max(15, round(seller_approval_rate * 0.80)),
        min(100, round(seller_approval_rate)),
    ]

    if seller_approval_rate >= 90:
        approval_caption = "Excellent approval rate. Most applications are approved on the first review."
    elif seller_approval_rate >= 75:
        approval_caption = "Most reviewed applications are approved after evaluation."
    elif seller_approval_rate >= 50:
        approval_caption = (
            "Approval rate is moderate. Review application quality regularly."
        )
    else:
        approval_caption = (
            "Approval rate is below expectations. Manual review is recommended."
        )

    # -----------------------------------------------------------------
    # OPTIMIZED: Average Verification Time calculation
    # Handled completely at the Database level using Aggregate & F-Expressions
    # -----------------------------------------------------------------
    reviewed_sellers = Seller.objects.filter(
        status__in=[Seller.Status.VERIFIED, Seller.Status.REJECTED]
    )

    avg_timedelta = reviewed_sellers.aggregate(
        avg_time=Avg(
            ExpressionWrapper(
                F("updated_at") - F("created_at"), output_field=DurationField()
            )
        )
    )["avg_time"]

    avg_verification_time = round(avg_timedelta.total_seconds() / 3600, 1) if avg_timedelta else 0

    verification_time_bars = [
        90,
        75,
        65,
        55,
        45,
        35,
        max(20, min(100, round((24 - min(avg_verification_time, 24)) / 24 * 100))),
    ]

    if avg_verification_time <= 12:
        verification_status = "d-success"
        verification_caption = "Applications are being reviewed quickly."
    elif avg_verification_time <= 24:
        verification_status = "d-warning"
        verification_caption = "Average review time is within the expected range."
    else:
        verification_status = "d-danger"
        verification_caption = "Verification queue is taking longer than expected."

    # ==========================================
    # 6. BUYERS & USERS (Activity, Growth & Status)
    # ==========================================
    total_buyers = User.objects.count()
    current_month_buyers = User.objects.filter(
        date_joined__gte=current_month_start
    ).count()
    previous_month_buyers = User.objects.filter(
        date_joined__gte=previous_month_start,
        date_joined__lt=current_month_start,
    ).count()

    buyers_change = _calculate_change(current_month_buyers, previous_month_buyers)

    total_active_buyers = User.objects.filter(
        account_status=User.AccountStatus.VERIFIED
    ).count()
    active_buyers_percentage = (
        round((total_active_buyers / total_buyers) * 100) if total_buyers > 0 else 0
    )
    buyers_progress = active_buyers_percentage

    if active_buyers_percentage >= 90:
        buyer_health_status = "Healthy"
        buyer_health_color = "healthy"
    elif active_buyers_percentage >= 75:
        buyer_health_status = "Needs Review"
        buyer_health_color = "attention"
    else:
        buyer_health_status = "Critical"
        buyer_health_color = "critical"

    current_month_users = (
        User.objects.filter(date_joined__gte=current_month_start)
        .exclude(account_status=User.AccountStatus.BLOCKED)
        .count()
    )

    previous_month_users = (
        User.objects.filter(
            date_joined__gte=previous_month_start, date_joined__lt=current_month_start
        )
        .exclude(account_status=User.AccountStatus.BLOCKED)
        .count()
    )

    users_change = _calculate_change(current_month_users, previous_month_users)

    new_users_today = (
        User.objects.exclude(account_status=User.AccountStatus.BLOCKED)
        .filter(date_joined__gte=today_start)
        .count()
    )

    new_users_yesterday = (
        User.objects.exclude(account_status=User.AccountStatus.BLOCKED)
        .filter(date_joined__gte=yesterday_start, date_joined__lt=today_start)
        .count()
    )

    new_users_change = _calculate_change(new_users_today, new_users_yesterday)

    current_total_users = User.objects.exclude(
        account_status=User.AccountStatus.BLOCKED
    ).count()
    previous_total_users = (
        User.objects.filter(date_joined__lt=thirty_days_ago)
        .exclude(account_status=User.AccountStatus.BLOCKED)
        .count()
    )

    user_growth_30d = _calculate_change(current_total_users, previous_total_users)

    if user_growth_30d >= 15:
        growth_trend = "Rapid growth"
    elif user_growth_30d >= 8:
        growth_trend = "Strong upward trend"
    elif user_growth_30d >= 3:
        growth_trend = "Steady upward trend"
    elif user_growth_30d > -3:
        growth_trend = "Stable"
    elif user_growth_30d > -10:
        growth_trend = "Gradual decline"
    else:
        growth_trend = "Significant decline"

    active_users_30d = (
        User.objects.filter(last_login__gte=thirty_days_ago)
        .exclude(account_status=User.AccountStatus.BLOCKED)
        .count()
    )

    previous_active_users_30d = (
        User.objects.filter(
            last_login__gte=sixty_days_ago,
            last_login__lt=thirty_days_ago,
        )
        .exclude(account_status=User.AccountStatus.BLOCKED)
        .count()
    )

    active_users_change = _calculate_change(active_users_30d, previous_active_users_30d)

    if active_users_change >= 15:
        active_users_trend = "Rapid increase"
    elif active_users_change >= 5:
        active_users_trend = "Steady upward trend"
    elif active_users_change > -5:
        active_users_trend = "Stable activity"
    elif active_users_change > -15:
        active_users_trend = "Slight decline"
    else:
        active_users_trend = "Significant decline"

    # Fetching overall total for distribution
    total_users = User.objects.count()
    status_distribution = []

    statuses = [
        ("Verified", User.AccountStatus.VERIFIED),
        ("Unverified", User.AccountStatus.UNVERIFIED),
        ("Suspended", User.AccountStatus.SUSPENDED),
        ("Deactivated", User.AccountStatus.DEACTIVATED),
        ("Blocked", User.AccountStatus.BLOCKED),
    ]

    for label, status in statuses:
        count = User.objects.filter(account_status=status).count()
        percentage = round((count / total_users) * 100) if total_users > 0 else 0
        status_distribution.append(
            {
                "label": label,
                "count": count,
                "percentage": percentage,
                "progress": percentage,
            }
        )

    total_pbuyers = (
        User.objects.filter(seller_profile__isnull=True)
        .exclude(account_status=User.AccountStatus.BLOCKED)
        .count()
    )
    total_psellers = Seller.objects.count()
    total_pmarketplace_users = total_pbuyers + total_psellers

    buyers_ppercentage = (
        round((total_pbuyers / total_pmarketplace_users) * 100)
        if total_pmarketplace_users > 0
        else 0
    )
    circumference = 2 * 3.14159265359 * 60
    buyers_donut_offset = circumference * (1 - buyers_ppercentage / 100)

    active_marketplace_users = (
        User.objects.filter(last_login__gte=thirty_days_ago)
        .exclude(
            account_status=User.AccountStatus.BLOCKED,
        )
        .count()
    )

    total_marketplace_users = User.objects.exclude(
        account_status=User.AccountStatus.BLOCKED,
    ).count()

    if total_marketplace_users > 0:
        active_marketplace_ratio = round(
            (active_marketplace_users / total_marketplace_users) * 100, 1
        )
    else:
        active_marketplace_ratio = 0

    active_ratio_bars = [
        max(20, round(active_marketplace_ratio * 0.60)),
        max(20, round(active_marketplace_ratio * 0.68)),
        max(20, round(active_marketplace_ratio * 0.75)),
        max(20, round(active_marketplace_ratio * 0.82)),
        max(20, round(active_marketplace_ratio * 0.90)),
        max(20, round(active_marketplace_ratio * 0.95)),
        min(100, round(active_marketplace_ratio)),
    ]

    if active_marketplace_ratio >= 80:
        marketplace_status = "d-success"
        marketplace_caption = (
            "Most marketplace accounts were active during the last 30 days."
        )
    elif active_marketplace_ratio >= 60:
        marketplace_status = "d-warning"
        marketplace_caption = (
            "Marketplace activity is healthy but has room for improvement."
        )
    else:
        marketplace_status = "d-danger"
        marketplace_caption = "Marketplace engagement is lower than expected."

    inactive_users_90d = (
        User.objects.filter(
            Q(last_login__lt=ninety_days_ago) | Q(last_login__isnull=True)
        )
        .exclude(account_status=User.AccountStatus.BLOCKED)
        .count()
    )

    total_active_users = User.objects.exclude(
        account_status=User.AccountStatus.BLOCKED
    ).count()

    if total_active_users > 0:
        inactive_percentage = round((inactive_users_90d / total_active_users) * 100, 1)
    else:
        inactive_percentage = 0

    inactive_user_bars = [
        max(15, round(inactive_percentage * 0.50)),
        max(15, round(inactive_percentage * 0.55)),
        max(15, round(inactive_percentage * 0.60)),
        max(15, round(inactive_percentage * 0.58)),
        max(15, round(inactive_percentage * 0.64)),
        max(15, round(inactive_percentage * 0.70)),
        max(15, min(100, round(inactive_percentage))),
    ]

    if inactive_percentage <= 10:
        inactive_status = "d-success"
        inactive_caption = "Very few users have been inactive for the last 90 days."
    elif inactive_percentage <= 25:
        inactive_status = "d-warning"
        inactive_caption = (
            "Some users have been inactive and may benefit from re-engagement."
        )
    else:
        inactive_status = "d-danger"
        inactive_caption = (
            "A significant number of users have been inactive for over 90 days."
        )

    # ==========================================
    # 7. FRAUD & SECURITY ALERTS
    # ==========================================
    total_suspended_accounts = User.objects.filter(
        account_status=User.AccountStatus.SUSPENDED
    ).count()
    current_month_suspended = User.objects.filter(
        account_status=User.AccountStatus.SUSPENDED,
        date_joined__gte=current_month_start,
    ).count()
    previous_month_suspended = User.objects.filter(
        account_status=User.AccountStatus.SUSPENDED,
        date_joined__gte=previous_month_start,
        date_joined__lt=current_month_start,
    ).count()

    suspended_change = _calculate_change(
        current_month_suspended, previous_month_suspended
    )

    open_fraud_alerts = User.objects.filter(
        account_status__in=[User.AccountStatus.SUSPENDED, User.AccountStatus.BLOCKED]
    ).count()

    fraud_alert_bars = [
        max(10, min(open_fraud_alerts * 8, 20)),
        max(10, min(open_fraud_alerts * 6, 15)),
        max(10, min(open_fraud_alerts * 10, 30)),
        max(10, min(open_fraud_alerts * 6, 18)),
        max(10, min(open_fraud_alerts * 8, 25)),
        max(10, min(open_fraud_alerts * 4, 12)),
        max(10, min(open_fraud_alerts * 18, 100)),
    ]

    if open_fraud_alerts == 0:
        fraud_status = "d-success"
        fraud_caption = "No suspicious accounts currently require manual review."
    elif open_fraud_alerts <= 5:
        fraud_status = "d-warning"
        fraud_caption = "A few flagged accounts are awaiting review."
    else:
        fraud_status = "d-danger"
        fraud_caption = "Multiple flagged accounts require immediate attention."

    security_recommendations = []
    unverified_users = User.objects.filter(
        account_status=User.AccountStatus.UNVERIFIED
    ).count()

    if unverified_users > 0:
        security_recommendations.append("Review unverified user accounts.")

    blocked_users = User.objects.filter(
        account_status=User.AccountStatus.BLOCKED
    ).count()
    if blocked_users > 0:
        security_recommendations.append("Audit blocked accounts.")

    if pending_sellers > 10:
        security_recommendations.append("Review pending seller applications.")

    if open_fraud_alerts > 0:
        security_recommendations.append("Investigate flagged accounts.")

    pending_recommendations = len(security_recommendations)

    security_bars = [40, 40, 40, 40, 40, 40, max(15, min(100, pending_recommendations * 20))]
    if pending_recommendations == 0:
        security_status = "d-success"
    elif pending_recommendations <= 2:
        security_status = "d-warning"
    else:
        security_status = "d-danger"

    if pending_recommendations:
        security_caption = security_recommendations[0]
    else:
        security_caption = "No security recommendations at this time."

    sales_chart_data = get_sales_chart_data()

    return {
        "admin": {
            "total_revenue": total_revenue,
            "revenue_change": round(percentage_change, 1),
            "revenue_increased": percentage_change >= 0,
            "total_orders": current_month_orders,
            "orders_change": round(orders_change, 1),
            "orders_increased": orders_change >= 0,
            "total_products": total_products,
            "products_change": round(products_change, 1),
            "products_increased": products_change >= 0,
            "total_sellers": total_sellers,
            "sellers_change": round(sellers_change, 1),
            "sellers_increased": sellers_change >= 0,
            "total_buyers": total_buyers,
            "buyers_change": round(buyers_change, 1),
            "buyers_increased": buyers_change >= 0,
            "pending_sellers": pending_sellers,
            "pending_sellers_change": pending_sellers_change,
            "pending_sellers_increased": pending_sellers_increased,
            "suspended_sellers": suspended_sellers,
            "suspended_sellers_change": suspended_sellers_change,
            "suspended_sellers_increased": suspended_sellers_increased,
            "pending_products": pending_products,
            "low_stock_products": low_stock_products,
            "today_sales": today_sales,
            "sales_change": round(sales_change, 1),
            "sales_increased": sales_change >= 0,
            "top_selling_categories": top_selling_categories,
            "latest_orders": latest_orders,
            "total_users": total_users,
            "users_change": round(users_change, 1),
            "users_increased": users_change >= 0,
            "total_verified_sellers": total_verified_sellers,
            "verified_sellers_change": round(verified_sellers_change, 1),
            "verified_sellers_increased": verified_sellers_change >= 0,
            "total_suspended_accounts": total_suspended_accounts,
            "suspended_change": round(suspended_change, 1),
            "suspended_increased": suspended_change >= 0,
            "new_users_today": new_users_today,
            "new_users_change": round(new_users_change, 1),
            "new_users_increased": new_users_change >= 0,
            "user_growth_30d": round(user_growth_30d, 1),
            "growth_trend": growth_trend,
            "active_users_30d": active_users_30d,
            "active_users_change": round(active_users_change, 1),
            "active_users_trend": active_users_trend,
            "active_buyers": total_active_buyers,
            "active_buyers_percentage": active_buyers_percentage,
            "buyers_progress": buyers_progress,
            "buyer_health_status": buyer_health_status,
            "buyer_health_color": buyer_health_color,
            "sellers_active_percentage": active_percentage,
            "seller_progress": seller_progress,
            "seller_health_status": seller_health_status,
            "seller_health_color": seller_health_color,
            "last_updated": timezone.now(),
            "reviewed_today": reviewed_today,
            "reviewed_percentage": reviewed_percentage,
            "seller_review_progress": reviewed_percentage,
            "seller_application_status": seller_application_status,
            "seller_application_color": seller_application_color,
            "status_distribution": status_distribution,
            "total_pbuyers": total_pbuyers,
            "total_psellers": total_psellers,
            "buyers_ppercentage": buyers_ppercentage,
            "buyers_donut_offset": round(buyers_donut_offset, 2),
            "seller_approval_rate": seller_approval_rate,
            "seller_approval_bars": seller_approval_bars,
            "approval_caption": approval_caption,
            "avg_verification_time": avg_verification_time,
            "verification_time_bars": verification_time_bars,
            "verification_status": verification_status,
            "verification_caption": verification_caption,
            "active_marketplace_ratio": active_marketplace_ratio,
            "active_ratio_bars": active_ratio_bars,
            "marketplace_status": marketplace_status,
            "marketplace_caption": marketplace_caption,
            "open_fraud_alerts": open_fraud_alerts,
            "fraud_alert_bars": fraud_alert_bars,
            "fraud_status": fraud_status,
            "fraud_caption": fraud_caption,
            "inactive_users_90d": inactive_users_90d,
            "inactive_percentage": inactive_percentage,
            "inactive_user_bars": inactive_user_bars,
            "inactive_status": inactive_status,
            "inactive_caption": inactive_caption,
            "pending_recommendations": pending_recommendations,
            "security_status": security_status,
            "security_bars": security_bars,
            "security_caption": security_caption,
            "sales_chart_data": sales_chart_data,
        },
        "activity_logs": ActivityLog.objects.select_related("actor")[:6],
        "user_activity_logs": ActivityLog.objects.select_related("actor")[:50],
        "recent_active_users": User.objects.select_related("seller_profile").order_by(
            "-last_login", "-date_joined"
        )[:8],
    }


# admin_panel/context_processors.py

from admin_panel.marketplace import get_marketplace_settings
from admin_panel.checkout import get_checkout_settings
from admin_panel.catalog import get_catalog_settings
from admin_panel.notification_settings import get_notification_settings
from admin_panel.settings_data import get_admin_settings_data
from admin_panel.services import get_store_settings


def marketplace(request):
    store_settings = get_store_settings()

    return {
        "marketplace": store_settings,
        "marketplace_settings": get_marketplace_settings(),
        "checkout_settings": get_checkout_settings(),
          "catalog_settings": get_catalog_settings(),
          "notification_settings": get_notification_settings(),
          "admin_settings_data": get_admin_settings_data(),
    }

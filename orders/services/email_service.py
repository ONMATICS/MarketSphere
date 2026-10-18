import logging

from notifications.emails.orders import (
    send_order_cancelled_email,
    send_order_delivered_email,
    send_order_placed_email,
)
from notifications.emails.sellers import (
    send_cancelled_order_email,
    send_delivered_order_email,
    send_new_order_email,
)
from orders.models import Order

logger = logging.getLogger(__name__)


def _send_order_created_emails(order: Order) -> None:
    """Send order placement emails to both the buyer and the seller."""
    for sender in (send_order_placed_email, send_new_order_email):
        try:
            sender(order)
        except Exception:
            logger.exception("Order-created email failed for %s", order.order_number)


def _send_cancelled_emails(order: Order) -> None:
    """Send order cancellation emails to the buyer and the seller."""
    reason = getattr(order, "cancellation_reason", None)
    for sender in (send_order_cancelled_email, send_cancelled_order_email):
        try:
            sender(order, reason)
        except Exception:
            logger.exception("Order-cancelled email failed for %s", order.order_number)


def _send_delivered_emails(order: Order) -> None:
    """Send order delivery confirmation emails to both parties."""
    for sender in (send_order_delivered_email, send_delivered_order_email):
        try:
            sender(order)
        except Exception:
            logger.exception("Order-delivered email failed for %s", order.order_number)
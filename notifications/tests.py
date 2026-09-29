from unittest.mock import Mock, patch

from django.db import transaction
from django.test import TestCase

from accounts.models import Seller, SellerSettings, User
from notifications.models import ActivityLog, Notification
from notifications.services.notifications import notify, schedule_low_stock_event
from orders.models import Order
from orders.services import update_order_status
from products.models import Product


class NotificationIntegrationTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="password"
        )
        self.seller_user = User.objects.create_user(
            username="seller", email="seller@example.com", password="password"
        )
        self.seller = Seller.objects.create(
            user=self.seller_user, store_name="Test Store", slug="test-store"
        )
        SellerSettings.objects.create(seller=self.seller)
        self.order = Order.objects.create(
            user=self.buyer,
            seller=self.seller,
            order_number="ORDER-1",
            shipping_name="Buyer Name",
            shipping_address="1 Test Street",
            shipping_city="Test City",
        )

    def test_notify_can_create_notification_email_and_activity_log(self):
        email_service = Mock()

        with self.captureOnCommitCallbacks(execute=True):
            notification = notify(
                user_id=self.buyer.id,
                notification_type=Notification.NotificationType.ORDER_CREATED,
                title="Order placed",
                message="Your order was placed.",
                audience=Notification.Audience.BUYER,
                email=True,
                email_service=email_service,
                email_object=self.order,
                activity=True,
                activity_category=ActivityLog.Category.ORDER,
                activity_action="ORDER_CREATED",
                activity_actor=self.buyer,
                activity_actor_type=ActivityLog.ActorType.BUYER,
                activity_target=self.order,
                activity_metadata={"order_number": self.order.order_number},
            )

        self.assertIsNotNone(notification)
        email_service.assert_called_once_with(self.order)
        activity = ActivityLog.objects.get(action="ORDER_CREATED")
        self.assertEqual(activity.actor, self.buyer)
        self.assertEqual(activity.target, self.order)
        self.assertEqual(activity.metadata["order_number"], "ORDER-1")

    def test_repeated_delivered_status_creates_one_event_and_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(
                update_order_status(
                    self.seller, self.order.order_number, Order.Status.DELIVERED
                ),
                1,
            )

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.seller_user,
                notification_type=Notification.NotificationType.ORDER_DELIVERED,
            ).count(),
            1,
        )

        with patch("orders.services.send_delivered_order_email") as seller_email:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(
                    update_order_status(
                        self.seller, self.order.order_number, Order.Status.DELIVERED
                    ),
                    0,
                )
            seller_email.assert_not_called()

    def test_low_stock_is_created_only_when_crossing_threshold(self):
        product = Product.objects.create(
            seller=self.seller,
            name="Test Product",
            slug="test-product",
            stock_quantity=4,
            min_stock_level=5,
        )

        with patch("notifications.emails.sellers.send_low_stock_email") as email:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    self.assertTrue(schedule_low_stock_event(product, 6, 4))
            email.assert_called_once_with(product)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.seller_user,
                notification_type=Notification.NotificationType.LOW_STOCK,
            ).count(),
            1,
        )

        with patch("notifications.emails.sellers.send_low_stock_email") as email:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    self.assertFalse(schedule_low_stock_event(product, 4, 3))
            email.assert_not_called()

# Create your tests here.

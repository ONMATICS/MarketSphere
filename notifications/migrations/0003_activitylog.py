from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "__latest__"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("notifications", "0002_notification_audience"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "actor_type",
                    models.CharField(
                        choices=[
                            ("ADMIN", "Admin"),
                            ("BUYER", "Buyer"),
                            ("SELLER", "Seller"),
                            ("SYSTEM", "System"),
                        ],
                        default="SYSTEM",
                        max_length=20,
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("ACCOUNT", "Account"),
                            ("SELLER", "Seller"),
                            ("PRODUCT", "Product"),
                            ("ORDER", "Order"),
                            ("SECURITY", "Security"),
                            ("SUPPORT", "Support"),
                            ("PAYMENT", "Payment"),
                            ("SYSTEM", "System"),
                        ],
                        max_length=20,
                    ),
                ),
                ("action", models.CharField(max_length=100)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("target_object_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "target_content_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_logs",
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["category", "-created_at"], name="notificatio_categor_56b7b1_idx"),
                    models.Index(fields=["actor", "-created_at"], name="notificatio_actor_i_d5b1fa_idx"),
                    models.Index(fields=["target_content_type", "target_object_id", "-created_at"], name="notificatio_target__3da1f3_idx"),
                ],
            },
        ),
    ]

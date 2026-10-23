from django.conf import settings
from django.db import models


class AdminAuditLog(models.Model):
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_logs",
    )

    action = models.CharField(max_length=50)
    section = models.CharField(max_length=50)
    setting_name = models.CharField(max_length=100)

    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.section}: {self.setting_name}"
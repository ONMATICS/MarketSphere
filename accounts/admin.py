from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from .models import (
    User, 
    Address, 
    Seller, 
    SellerApplication, 
    SellerApplicationDocument, 
    SellerApplicationFlag, 
    SellerSettings, 
    SellerProfile
)

# Register your models here.

class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name", "email", "contact", "profile_image_url")}),
        ("Account", {"fields": ("account_status", "is_active")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "is_active", "is_staff"),
        }),
    )

    list_display = (
        "username",
        "email",
        "account_status",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "account_status",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "username",
        "email",
        "contact",
    )

    list_editable = (
        "account_status",
        "is_active",
    )

    ordering = (
        "username",
    )

    _protected_fields = {"is_staff", "is_superuser", "groups", "user_permissions"}

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            if request.user.is_superuser:
                return self.add_fieldsets
            return (
                (None, {
                    "classes": ("wide",),
                    "fields": ("username", "email", "password1", "password2", "is_active"),
                }),
            )

        if request.user.is_superuser:
            return super().get_fieldsets(request, obj)

        return (
            (None, {"fields": ("username", "password")}),
            ("Personal information", {"fields": ("first_name", "last_name", "email", "contact", "profile_image_url")}),
            ("Account", {"fields": ("account_status", "is_active")}),
            ("Important dates", {"fields": ("last_login", "date_joined")}),
        )

    def get_form(self, request, obj=None, **kwargs):
        if not request.user.is_superuser:
            excluded = set(kwargs.get("exclude") or ())
            excluded.update(self._protected_fields)
            kwargs["exclude"] = tuple(excluded)
        return super().get_form(request, obj, **kwargs)

    def has_change_permission(self, request, obj=None):
        if obj is not None and (obj.is_superuser or obj == request.user) and not request.user.is_superuser:
            return obj == request.user
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)


class SuperuserOnlyGroupAdmin(admin.ModelAdmin):
    """Expose group/role administration only to the authorized superuser."""

    list_display = ("name",)
    search_fields = ("name",)

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "address_type",
        "full_name",
        "city",
        "is_default",
    )

    list_filter = (
        "address_type",
        "is_default",
        "city",
    )

    search_fields = (
        "user__username",
        "full_name",
        "phone",
        "city",
    )

    list_editable = (
        "is_default",
    )

    ordering = (
        "-is_default",
        "-created_at",
    )


class SellerAdmin(admin.ModelAdmin):
    list_display = (
        "store_name",
        "user",
        "store_email",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "store_name",
        "user__username",
        "store_email",
    )

    prepopulated_fields = {
        "slug": ("store_name",)
    }

    list_editable = (
        "status",
    )

    ordering = (
        "-created_at",
    )


class SellerApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "seller",
        "status",
        "priority",
        "assigned_to",
        "submitted_at",
    )

    list_filter = (
        "status",
        "priority",
        "assigned_to",
    )

    search_fields = (
        "seller__store_name",
        "referral_code",
    )

    list_editable = (
        "status",
        "priority",
    )

    ordering = (
        "-created_at",
    )


class SellerApplicationDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "document_type",
        "verified",
        "uploaded_at",
    )

    list_filter = (
        "document_type",
        "verified",
    )

    search_fields = (
        "application__seller__store_name",
    )

    list_editable = (
        "verified",
    )

    ordering = (
        "-uploaded_at",
    )


class SellerApplicationFlagAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "title",
        "severity",
        "resolved",
    )

    list_filter = (
        "severity",
        "resolved",
    )

    search_fields = (
        "title",
        "application__seller__store_name",
    )

    list_editable = (
        "resolved",
    )

    ordering = (
        "-created_at",
    )


class SellerSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "seller",
        "default_handling_time",
        "business_registration_verified",
        "bank_account_verified",
        "address_verified",
    )

    list_filter = (
        "business_registration_verified",
        "bank_account_verified",
        "address_verified",
    )

    search_fields = (
        "seller__store_name",
        "business_registration_number",
        "tax_id",
    )

    list_editable = (
        "business_registration_verified",
        "bank_account_verified",
        "address_verified",
    )

    ordering = (
        "seller",
    )


class SellerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "seller",
        "business_category",
        "business_type",
        "national_id_number",
    )

    list_filter = (
        "business_category",
        "business_type",
    )

    search_fields = (
        "seller__store_name",
        "national_id_number",
        "business_category",
    )

    ordering = (
        "seller",
    )


admin.site.register(User, UserAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(Seller, SellerAdmin)
admin.site.register(SellerApplication, SellerApplicationAdmin)
admin.site.register(SellerApplicationDocument, SellerApplicationDocumentAdmin)
admin.site.register(SellerApplicationFlag, SellerApplicationFlagAdmin)
admin.site.register(SellerSettings, SellerSettingsAdmin)
admin.site.register(SellerProfile, SellerProfileAdmin)

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass
admin.site.register(Group, SuperuserOnlyGroupAdmin)

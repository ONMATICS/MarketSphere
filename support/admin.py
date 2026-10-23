from django.contrib import admin

from .models.support_models import SupportMessage, SupportRequest
from .models.review_models import Review, ReviewReport

class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = [
        "sender",
        "sender_type",
        "created_at",
    ]


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "subject",
        "user",
        "request_type",
        "category",
        "status",
        "created_at",
        "updated_at",
    ]

    list_filter = [
        "request_type",
        "category",
        "status",
        "created_at",
    ]

    search_fields = [
        "subject",
        "message",
        "user__username",
        "user__email",
        "related_order__order_number",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    inlines = [
        SupportMessageInline,
    ]

    ordering = [
        "-updated_at",
    ]


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):

    list_display = [
        "request",
        "sender",
        "sender_type",
        "created_at",
    ]

    list_filter = [
        "sender_type",
        "created_at",
    ]

    search_fields = [
        "message",
        "request__subject",
        "sender__username",
        "sender__email",
    ]

    readonly_fields = [
        "created_at",
    ]



class ReviewReportInline(admin.TabularInline):
    """
    Allows admins to see all reports for a specific review 
    directly inside the Review admin page.
    """
    model = ReviewReport
    extra = 0
    readonly_fields = ("user", "reason", "description", "created_at")
    fields = ("user", "reason", "description", "status", "created_at")
    can_delete = False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id", 
        "user", 
        "product", 
        "rating", 
        "title", 
        "helpful_count", 
        "created_at"
    )
    list_display_links = ("id", "user", "title")
    list_filter = ("rating", "created_at")
    search_fields = (
        "title", 
        "description", 
        "user__username", 
        "user__email", 
        "product__name", 
        "order_item__id"
    )
    readonly_fields = ("created_at", "updated_at")
    
    # Use raw_id_fields for foreign keys to prevent the admin from 
    # loading a massive dropdown of all users, products, or order items.
    raw_id_fields = ("user", "product", "order_item")
    
    inlines = [ReviewReportInline]
    date_hierarchy = "created_at"
    
    fieldsets = (
        ("Review Details", {
            "fields": ("user", "product", "order_item", "rating", "title", "description")
        }),
        ("Media & Metrics", {
            "fields": ("image", "helpful_count")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = (
        "id", 
        "review", 
        "user", 
        "reason", 
        "status", 
        "created_at"
    )
    list_display_links = ("id", "review")
    list_filter = ("status", "reason", "created_at")
    search_fields = (
        "reason", 
        "description", 
        "user__username", 
        "user__email", 
        "review__title", 
        "review__id"
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("review", "user")
    date_hierarchy = "created_at"
    
    # Custom bulk actions for rapid status updates
    actions = ['mark_as_reviewed', 'mark_as_dismissed', 'mark_as_action_taken']

    @admin.action(description='Mark selected reports as Reviewed')
    def mark_as_reviewed(self, request, queryset):
        queryset.update(status=ReviewReport.Status.REVIEWED)

    @admin.action(description='Mark selected reports as Dismissed')
    def mark_as_dismissed(self, request, queryset):
        queryset.update(status=ReviewReport.Status.DISMISSED)

    @admin.action(description='Mark selected reports as Action Taken')
    def mark_as_action_taken(self, request, queryset):
        queryset.update(status=ReviewReport.Status.ACTION_TAKEN)
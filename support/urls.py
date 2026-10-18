from django.urls import path
from . import views

urlpatterns = [
    path("help-support/", views.help_and_support_view, name="help-support"),
    path("help/topic/<slug:slug>/", views.help_topic_detail_view, name="help-topic"),
    path(
        "help/article/<slug:slug>/", views.help_article_detail_view, name="help-article"
    ),
    path("api/requests/create/", views.create_support_request_view, name="create_request"),
    path("api/requests/", views.support_requests_view, name="support_requests"),
    path("api/requests/<int:request_id>/", views.support_request_detail_view, name="support_request_detail"),
]

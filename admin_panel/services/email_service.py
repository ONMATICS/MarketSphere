from typing import BinaryIO

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from accounts.models import User


def send_admin_email(
    *, user: User, subject: str, message: str,
    button_text: str | None = None, button_url: str | None = None,
    attachments: list[BinaryIO] | None = None
) -> None:
    """Transmit a branded Marketplace email template asynchronously to an individual user."""
    context = {"user": user, "message": message, "button_text": button_text, "button_url": button_url}
    html_body = render_to_string("email_components/send_email.html", context)
    text_body = render_to_string("email_components/send_email.txt", context)

    email = EmailMultiAlternatives(subject=subject, body=text_body, from_email=settings.DEFAULT_FROM_EMAIL, to=[user.email])
    email.attach_alternative(html_body, "text/html")

    if attachments:
        for uploaded_file in attachments:
            email.attach(uploaded_file.name, uploaded_file.read(), uploaded_file.content_type)

    email.send(fail_silently=False)
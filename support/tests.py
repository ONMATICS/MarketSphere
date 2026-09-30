from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models.support import SupportRequest


class SupportFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="support-user",
            email="support@example.com",
            password="test-password-123",
        )
        self.client.force_login(self.user)

    def test_support_page_uses_real_requests_and_not_demo_requests(self):
        response = self.client.get(reverse("help-support"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SR-10482")

        request = SupportRequest.objects.create(
            user=self.user,
            request_type=SupportRequest.RequestType.CONTACT,
            category=SupportRequest.Category.GENERAL,
            subject="Need help",
            message="Please help me.",
        )
        response = self.client.get(reverse("help-support"))
        self.assertContains(response, request.subject)

    def test_create_and_list_support_request(self):
        response = self.client.post(
            reverse("create_request"),
            {
                "request_type": "contact",
                "category": "general",
                "subject": "Question about my account",
                "message": "Please explain this account setting.",
                "preferred_contact_method": "in_app",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["success"])
        self.assertEqual(SupportRequest.objects.count(), 1)
        self.assertEqual(self.user.support_requests.first().messages.count(), 1)

        response = self.client.get(reverse("support_requests"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["requests"]), 1)

    def test_request_detail_is_private_to_owner(self):
        request = SupportRequest.objects.create(
            user=self.user,
            request_type=SupportRequest.RequestType.PROBLEM,
            category=SupportRequest.Category.TECHNICAL,
            subject="Broken page",
            message="The page is not loading.",
        )
        response = self.client.get(
            reverse("support_request_detail", kwargs={"request_id": request.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request"]["id"], request.id)

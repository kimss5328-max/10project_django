from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AccountTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        r = self.client.post(reverse("signup"), {
            "username": "alice", "email": "",
            "password1": "Str0ngPass!23", "password2": "Str0ngPass!23"})
        self.assertRedirects(r, reverse("home"))
        self.assertTrue(User.objects.filter(username="alice").exists())

    def test_login(self):
        User.objects.create_user("bob", password="Str0ngPass!23")
        r = self.client.post(reverse("login"), {"username": "bob", "password": "Str0ngPass!23"})
        self.assertRedirects(r, reverse("home"))

    def test_home_requires_login(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)
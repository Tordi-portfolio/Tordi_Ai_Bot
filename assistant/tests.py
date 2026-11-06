from email.message import EmailMessage as PyEmail
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from . import ai, services
from .emailer import process_message
from .models import ChatSession, InboundEmail, KnowledgeEntry


def raw_email(sender="Ada <ada@example.com>", subject="Canada visa", body="How do I get a Canada study visa?", **headers):
    m = PyEmail()
    m["From"] = sender
    m["To"] = "company@gmail.com"
    m["Subject"] = subject
    m["Message-ID"] = headers.pop("message_id", "<abc123@example.com>")
    for k, v in headers.items():
        m[k.replace("_", "-")] = v
    m.set_content(body)
    return m.as_bytes()


@override_settings(
    GMAIL_ADDRESS="company@gmail.com", SITE_URL="https://visa.example.com", WHATSAPP_NUMBER="2348012345678",
    COMPANY_NAME="Test Visa Co", QUALIFY_SCORE=7, MAX_REPLIES_PER_SENDER_PER_DAY=3,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class FlowTests(TestCase):
    def setUp(self):
        KnowledgeEntry.objects.create(title="Canada", content="We process Canada study permits.")

    @override_settings(AUTO_SEND_REPLIES=True)
    @patch("assistant.ai._call_model", return_value="Hello Ada, we help with Canada study permits. Please chat with our assistant.")
    def test_email_gets_reply_with_chat_link(self, _):
        self.assertTrue(process_message(raw_email()))
        self.assertEqual(len(mail.outbox), 1)
        out = mail.outbox[0]
        self.assertEqual(out.to, ["ada@example.com"])
        self.assertEqual(out.subject, "Re: Canada visa")
        session = ChatSession.objects.get()
        self.assertIn(f"https://visa.example.com/chat/{session.token}/", out.body)
        self.assertEqual(out.extra_headers["In-Reply-To"], "<abc123@example.com>")
        self.assertEqual(InboundEmail.objects.get().status, "replied")

    @override_settings(AUTO_SEND_REPLIES=True)
    @patch("assistant.ai._call_model", return_value="Hi")
    def test_same_email_not_answered_twice(self, _):
        process_message(raw_email())
        process_message(raw_email())
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(AUTO_SEND_REPLIES=True)
    @patch("assistant.ai._call_model", return_value="Hi")
    def test_noreply_and_auto_mail_skipped(self, ai_mock):
        process_message(raw_email(sender="noreply@shop.com", message_id="<1@x>"))
        process_message(raw_email(message_id="<2@x>", Auto_Submitted="auto-generated"))
        self.assertEqual(len(mail.outbox), 0)
        ai_mock.assert_not_called()
        self.assertEqual(InboundEmail.objects.filter(status="skipped").count(), 2)

    @override_settings(AUTO_SEND_REPLIES=True, MAX_REPLIES_PER_SENDER_PER_DAY=2)
    @patch("assistant.ai._call_model", return_value="Hi")
    def test_loop_protection_limit(self, _):
        for i in range(4):
            process_message(raw_email(message_id=f"<m{i}@x>"))
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(AUTO_SEND_REPLIES=False)
    @patch("assistant.ai._call_model", return_value="Hi")
    def test_draft_mode_does_not_send(self, _):
        process_message(raw_email())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(InboundEmail.objects.get().status, "draft")

    @override_settings(AUTO_SEND_REPLIES=True)
    @patch("assistant.ai._call_model", side_effect=RuntimeError("API down"))
    def test_ai_failure_retries_without_sending(self, _):
        self.assertFalse(process_message(raw_email()))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(InboundEmail.objects.get().status, "failed")

    @patch("assistant.ai._call_model")
    def test_chat_qualifies_and_redirects_to_whatsapp(self, model):
        session = services.create_session()
        url = reverse("chat_send", args=[session.token])

        model.return_value = '{"reply":"Which country?","lead_score":2,"ready_for_human":false,"name":null,"destination":null,"visa_type":null,"summary":""}'
        r = self.client.post(url, {"message": "hi"}, content_type="application/json").json()
        self.assertFalse(r["qualified"])
        self.assertIsNone(r["whatsapp_url"])
        self.assertEqual(self.client.get(reverse("whatsapp_redirect", args=[session.token])).status_code, 302)
        self.assertNotIn("wa.me", self.client.get(reverse("whatsapp_redirect", args=[session.token]))["Location"])

        model.return_value = ('```json\n{"reply":"Connecting you to an advisor on WhatsApp.","lead_score":9,"ready_for_human":true,'
                              '"name":"Ada","destination":"Canada","visa_type":"Study","summary":"Ada wants a Canada study visa."}\n```')
        r = self.client.post(url, {"message": "I want to apply for Canada study visa now, what do I pay?"}, content_type="application/json").json()
        self.assertTrue(r["qualified"])
        session.refresh_from_db()
        self.assertEqual(session.status, "qualified")
        self.assertEqual(session.destination, "Canada")

        resp = self.client.get(r["whatsapp_url"])
        self.assertTrue(resp["Location"].startswith("https://wa.me/2348012345678?text="))
        session.refresh_from_db()
        self.assertEqual(session.status, "handed_off")

    @patch("assistant.ai._call_model", return_value='{"reply":"Sure","lead_score":10,"ready_for_human":true}')
    def test_score_below_threshold_blocks_handoff(self, _):
        with override_settings(QUALIFY_SCORE=11):
            session = services.create_session()
            r = services.handle_user_message(session, "ready to pay")
            self.assertFalse(r["qualified"])

    @patch("assistant.ai._call_model", return_value="plain text, not json")
    def test_non_json_model_output_still_replies(self, _):
        session = services.create_session()
        r = services.handle_user_message(session, "hello")
        self.assertEqual(r["reply"], "plain text, not json")
        self.assertFalse(r["qualified"])

    def test_chat_page_and_home_render(self):
        session = services.create_session()
        self.assertContains(self.client.get(reverse("chat_page", args=[session.token])), "Test Visa Co")
        self.assertEqual(self.client.get("/").status_code, 200)
        r = self.client.post(reverse("start_chat"))
        self.assertEqual(r.status_code, 302)


@override_settings(GMAIL_ADDRESS="company@gmail.com", AUTO_SEND_REPLIES=True, SITE_URL="https://x.example.com",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class QuotaTests(TestCase):
    @patch("assistant.ai._call_model", side_effect=ai.AIRateLimited("quota"))
    def test_quota_keeps_email_unread_without_burning_attempts(self, _):
        with self.assertRaises(ai.AIRateLimited):
            process_message(raw_email())
        inbound = InboundEmail.objects.get()
        self.assertEqual(inbound.attempts, 0)
        self.assertEqual(inbound.status, "pending")
        with patch("assistant.ai._call_model", return_value="Hello"):
            self.assertTrue(process_message(raw_email()))
        self.assertEqual(len(mail.outbox), 1)

    @patch("assistant.ai._call_model", side_effect=ai.AIRateLimited("quota"))
    def test_chat_shows_busy_message_on_quota(self, _):
        session = services.create_session()
        r = self.client.post(reverse("chat_send", args=[session.token]), {"message": "hi"}, content_type="application/json")
        self.assertEqual(r.status_code, 429)

    def test_gemini_request_shape(self):
        import io, json
        from unittest.mock import MagicMock
        captured = {}

        def fake_urlopen(req, timeout=0):
            captured["body"] = json.loads(req.data)
            captured["key"] = req.get_header("X-goog-api-key")
            resp = MagicMock()
            resp.read.return_value = json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = lambda *a: False
            return resp

        with override_settings(GEMINI_API_KEY="k123", AI_MODEL="gemini-2.5-flash"), patch("urllib.request.urlopen", fake_urlopen):
            out = ai._call_model("sys", [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}], json_mode=True)
        self.assertEqual(out, "ok")
        self.assertEqual(captured["key"], "k123")
        self.assertEqual([c["role"] for c in captured["body"]["contents"]], ["user", "model"])
        self.assertEqual(captured["body"]["generationConfig"]["responseMimeType"], "application/json")

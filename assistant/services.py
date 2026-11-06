"""Business logic: chat turns, lead qualification, WhatsApp link."""
import logging
from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from . import ai
from .models import ChatMessage, ChatSession

log = logging.getLogger(__name__)


def greeting_text(session=None):
    name = f" {session.name}" if session and session.name else ""
    return (
        f"Hello{name}! Welcome to {settings.COMPANY_NAME}. "
        "Ask me anything about our visa services, or tell me which country you want to travel to."
    )


def create_session(email="", name=""):
    session = ChatSession.objects.create(email=email, name=name)
    ChatMessage.objects.create(session=session, role="assistant", content=greeting_text(session))
    return session


def _clean(value, limit=150):
    if not value or not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def handle_user_message(session, text):
    """Store the visitor's message, ask the AI, update the lead, return a dict for the browser."""
    ChatMessage.objects.create(session=session, role="user", content=text)
    data = ai.chat_turn(session)
    reply = _clean(data.get("reply"), 4000) or "Sorry, could you rephrase that?"
    ChatMessage.objects.create(session=session, role="assistant", content=reply)

    for field in ("name", "destination", "visa_type"):
        value = _clean(data.get(field))
        if value:
            setattr(session, field, value)
    summary = _clean(data.get("summary"), 1000)
    if summary:
        session.summary = summary

    score = data.get("lead_score")
    if isinstance(score, (int, float)):
        session.lead_score = max(0, min(10, int(score)))

    newly_qualified = False
    if session.status == ChatSession.Status.NEW:
        session.status = ChatSession.Status.CHATTING
    if (
        session.status == ChatSession.Status.CHATTING
        and data.get("ready_for_human") is True
        and session.lead_score >= settings.QUALIFY_SCORE
    ):
        session.status = ChatSession.Status.QUALIFIED
        session.qualified_at = timezone.now()
        newly_qualified = True
    session.save()

    if newly_qualified:
        notify_admin(session)

    return {
        "reply": reply,
        "qualified": session.is_qualified,
        "whatsapp_url": reverse("whatsapp_redirect", args=[session.token]) if session.is_qualified else None,
    }


def notify_admin(session):
    if not settings.ADMIN_NOTIFY_EMAIL:
        return
    try:
        send_mail(
            subject=f"New qualified client: {session.name or session.email or 'Visitor'}",
            message=(
                f"Name: {session.name or '-'}\nEmail: {session.email or '-'}\n"
                f"Destination: {session.destination or '-'}\nVisa type: {session.visa_type or '-'}\n"
                f"Lead score: {session.lead_score}/10\n\nSummary:\n{session.summary or '-'}\n\n"
                f"Reference: {str(session.token)[:8]}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_NOTIFY_EMAIL],
        )
    except Exception:  # never break the chat because a notification failed
        log.exception("Could not send admin notification")


def whatsapp_link(session):
    parts = [f"Hello {settings.COMPANY_NAME}"]
    if session.name:
        parts.append(f"my name is {session.name}")
    need = " ".join(p for p in (session.visa_type, f"visa for {session.destination}" if session.destination else "") if p)
    if need:
        parts.append(f"I'm interested in: {need}")
    text = ", ".join(parts) + f". (Ref: {str(session.token)[:8]})"
    return f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={quote(text)}"

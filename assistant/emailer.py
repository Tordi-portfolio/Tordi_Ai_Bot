"""Reads new emails from Gmail (IMAP), asks the AI for a reply, sends it (SMTP)."""
import hashlib
import imaplib
import logging
import re
from datetime import timedelta
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils import timezone

from . import ai
from .models import ChatMessage, ChatSession, InboundEmail

log = logging.getLogger(__name__)

NO_REPLY_NAMES = ("noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster", "bounce", "notifications")
MAX_ATTEMPTS = 3


# ------------------------------------------------------------------ parsing helpers
def _decode_header(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _decode_part(part):
    payload = part.get_payload(decode=True) or b""
    try:
        return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _strip_html(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", html)
    return re.sub(r"<[^>]+>", "", html)


def extract_text(msg):
    plain = html = None
    for part in msg.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain" and plain is None:
            plain = _decode_part(part)
        elif ctype == "text/html" and html is None:
            html = _decode_part(part)
    return plain if plain is not None else _strip_html(html or "")


def trim_quoted(text, limit=4000):
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^On .+wrote:$", stripped) or stripped.startswith("-----Original Message-----"):
            break
        if stripped.startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept).strip()[:limit]


def skip_reason(msg, sender):
    local = sender.split("@")[0].lower()
    if sender.lower() == settings.GMAIL_ADDRESS.lower():
        return "sent by our own mailbox"
    if any(n in local for n in NO_REPLY_NAMES):
        return "no-reply / system sender"
    auto = (msg.get("Auto-Submitted") or "no").lower()
    if auto != "no":
        return "automatic message"
    if (msg.get("Precedence") or "").lower() in ("bulk", "junk", "list", "auto_reply"):
        return "bulk / list mail"
    if msg.get("List-Id") or msg.get("X-Autoreply") or msg.get("X-Autorespond"):
        return "mailing list / autoresponder"
    return ""


# ------------------------------------------------------------------ sending
def build_reply_text(body, session):
    link = settings.SITE_URL + reverse("chat_page", args=[session.token])
    return (
        f"{body.strip()}\n\nContinue the conversation with our assistant here:\n{link}\n\n"
        f"Best regards,\n{settings.COMPANY_NAME} Team"
    )


def send_reply(inbound):
    subject = inbound.subject or "Your enquiry"
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    headers = {"Auto-Submitted": "auto-replied"}
    if inbound.message_id and not inbound.message_id.startswith("generated-"):
        headers["In-Reply-To"] = inbound.message_id
        headers["References"] = inbound.message_id
    EmailMessage(
        subject=subject,
        body=inbound.reply_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[inbound.sender],
        headers=headers,
    ).send()
    inbound.status = InboundEmail.Status.REPLIED
    inbound.replied_at = timezone.now()
    inbound.error = ""
    inbound.save()


# ------------------------------------------------------------------ main logic
def process_message(raw_bytes):
    """Handle one raw email. Returns True when finished (mark as read), False to retry later."""
    msg = message_from_bytes(raw_bytes)
    name, sender = parseaddr(_decode_header(msg.get("From")))
    sender = sender.strip().lower()
    subject = _decode_header(msg.get("Subject"))[:500]
    message_id = (msg.get("Message-ID") or "").strip()[:255]
    if not sender:
        return True
    body = trim_quoted(extract_text(msg))
    if not message_id:
        digest = hashlib.sha256(f"{sender}{subject}{msg.get('Date')}{body}".encode()).hexdigest()[:40]
        message_id = f"generated-{digest}"

    inbound, _ = InboundEmail.objects.get_or_create(
        message_id=message_id,
        defaults={"sender": sender, "sender_name": name[:150], "subject": subject, "body": body},
    )
    if inbound.status in (InboundEmail.Status.REPLIED, InboundEmail.Status.SKIPPED, InboundEmail.Status.DRAFT):
        return True
    if inbound.attempts >= MAX_ATTEMPTS:
        return True

    reason = skip_reason(msg, sender)
    if not reason:
        since = timezone.now() - timedelta(hours=24)
        recent = InboundEmail.objects.filter(
            sender__iexact=sender, status=InboundEmail.Status.REPLIED, replied_at__gte=since
        ).count()
        if recent >= settings.MAX_REPLIES_PER_SENDER_PER_DAY:
            reason = "reply limit reached for this sender today"
    if not body.strip():
        reason = reason or "empty message"
    if reason:
        inbound.status = InboundEmail.Status.SKIPPED
        inbound.skip_reason = reason
        inbound.save()
        return True

    try:
        if not inbound.reply_text:
            ai_body = ai.generate_email_reply(name, subject, body)
            if not ai_body:
                raise ValueError("The AI returned an empty reply")
            session = (
                ChatSession.objects.filter(email__iexact=sender, created__gte=timezone.now() - timedelta(days=30))
                .order_by("-created")
                .first()
            )
            if session is None:
                session = ChatSession.objects.create(email=sender, name=name[:150])
            if not session.messages.exists():
                ChatMessage.objects.create(
                    session=session, role="assistant",
                    content=f"Hello{' ' + session.name if session.name else ''}! Welcome to {settings.COMPANY_NAME}.",
                )
            ChatMessage.objects.create(session=session, role="user", content=f"(Email) {subject}\n\n{body}"[:4000])
            ChatMessage.objects.create(session=session, role="assistant", content=ai_body)
            inbound.session = session
            inbound.reply_text = build_reply_text(ai_body, session)
            inbound.save()

        if settings.AUTO_SEND_REPLIES:
            send_reply(inbound)
        else:
            inbound.status = InboundEmail.Status.DRAFT
            inbound.save()
        return True
    except ai.AIRateLimited as exc:
        # Quota used up: keep the email unread and unpenalised, try again on a later poll.
        inbound.status = InboundEmail.Status.PENDING
        inbound.error = str(exc)[:1000]
        inbound.save()
        raise
    except Exception as exc:
        log.exception("Failed to process email %s", message_id)
        inbound.attempts += 1
        inbound.status = InboundEmail.Status.FAILED
        inbound.error = str(exc)[:1000]
        inbound.save()
        return inbound.attempts >= MAX_ATTEMPTS


def process_inbox(limit=20):
    """Connect to Gmail, process unread emails. Returns the number handled."""
    imap = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
    handled = 0
    try:
        imap.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        imap.select("INBOX")
        _, data = imap.search(None, "UNSEEN")
        for num in data[0].split()[:limit]:
            _, parts = imap.fetch(num, "(BODY.PEEK[])")
            raw = parts[0][1]
            try:
                finished = process_message(raw)
            except ai.AIRateLimited:
                log.warning("Gemini quota reached; stopping this round, will retry on the next poll")
                break
            if finished:
                imap.store(num, "+FLAGS", "\\Seen")
            handled += 1
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return handled

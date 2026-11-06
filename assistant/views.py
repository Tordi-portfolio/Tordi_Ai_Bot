import json
import logging

from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import services
from .ai import AIRateLimited
from .models import ChatSession

log = logging.getLogger(__name__)


@require_GET
def home(request):
    return render(request, "assistant/home.html")


@require_POST
def start_chat(request):
    session = services.create_session()
    return redirect("chat_page", token=session.token)


@require_GET
def chat_page(request, token):
    session = get_object_or_404(ChatSession, token=token)
    return render(
        request,
        "assistant/chat.html",
        {
            "session": session,
            "messages": session.messages.all(),
            "qualified": session.is_qualified,
        },
    )


@require_POST
def chat_send(request, token):
    session = get_object_or_404(ChatSession, token=token)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)
    text = (payload.get("message") or "").strip()
    if not text:
        return JsonResponse({"error": "Please type a message."}, status=400)
    if len(text) > 1500:
        return JsonResponse({"error": "That message is too long. Please shorten it."}, status=400)
    if session.messages.filter(role="user").count() >= settings.CHAT_MAX_USER_MESSAGES:
        return JsonResponse({"error": "This chat has reached its message limit. Please contact us by email."}, status=429)
    try:
        result = services.handle_user_message(session, text)
    except AIRateLimited as exc:
        log.warning("Gemini quota reached: %s", exc)
        message = "Our assistant is very busy right now. Please try again in a minute."
        if settings.DEBUG:
            message += f" [DEBUG: {exc}]"
        return JsonResponse({"error": message}, status=429)
    except Exception as exc:
        log.exception("Chat failed")  # the full error now appears in your terminal
        message = "The assistant is unavailable right now. Please try again in a moment."
        if settings.DEBUG:  # only while DJANGO_DEBUG=True: shows the real reason in the chat
            message += f" [DEBUG: {exc}]"
        return JsonResponse({"error": message}, status=502)
    return JsonResponse(result)


@require_GET
def whatsapp_redirect(request, token):
    session = get_object_or_404(ChatSession, token=token)
    if not session.is_qualified:
        return redirect("chat_page", token=session.token)
    if session.status == ChatSession.Status.QUALIFIED:
        session.status = ChatSession.Status.HANDED_OFF
        session.save(update_fields=["status", "updated"])
    return HttpResponseRedirect(services.whatsapp_link(session))
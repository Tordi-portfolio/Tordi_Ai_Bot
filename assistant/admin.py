from django.contrib import admin, messages

from .emailer import send_reply
from .models import ChatMessage, ChatSession, InboundEmail, KnowledgeEntry

admin.site.site_header = "Visa AI Assistant"
admin.site.site_title = "Visa AI Assistant"


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "updated")
    list_filter = ("is_active",)
    search_fields = ("title", "content")


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    can_delete = False
    readonly_fields = ("role", "content", "created")


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "email", "destination", "visa_type", "lead_score", "status", "updated")
    list_filter = ("status",)
    search_fields = ("name", "email", "destination", "visa_type", "summary")
    ordering = ("-status", "-lead_score", "-updated")
    readonly_fields = ("token", "created", "updated", "qualified_at")
    inlines = [ChatMessageInline]


@admin.register(InboundEmail)
class InboundEmailAdmin(admin.ModelAdmin):
    list_display = ("sender", "subject", "status", "skip_reason", "received_at", "replied_at")
    list_filter = ("status",)
    search_fields = ("sender", "subject", "body")
    readonly_fields = ("message_id", "sender", "sender_name", "subject", "body", "session", "error", "attempts", "received_at", "replied_at")
    actions = ["send_selected_drafts"]

    @admin.action(description="Send selected drafts")
    def send_selected_drafts(self, request, queryset):
        sent = 0
        for inbound in queryset.filter(status=InboundEmail.Status.DRAFT):
            try:
                send_reply(inbound)
                sent += 1
            except Exception as exc:
                inbound.error = str(exc)[:1000]
                inbound.status = InboundEmail.Status.FAILED
                inbound.save()
                self.message_user(request, f"Could not send to {inbound.sender}: {exc}", level=messages.ERROR)
        self.message_user(request, f"{sent} reply(ies) sent.")

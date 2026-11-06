import uuid

from django.db import models


class KnowledgeEntry(models.Model):
    """One piece of company information the AI is allowed to use.
    Add/edit these in the admin: services, countries, requirements, fees, office hours, FAQs..."""

    title = models.CharField(max_length=200)
    content = models.TextField(help_text="Plain text. Be specific: the AI will only state what is written here.")
    is_active = models.BooleanField(default=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name_plural = "Knowledge entries"

    def __str__(self):
        return self.title


class ChatSession(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CHATTING = "chatting", "Chatting"
        QUALIFIED = "qualified", "Qualified (serious client)"
        HANDED_OFF = "handed_off", "Opened WhatsApp"

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(blank=True)
    name = models.CharField(max_length=150, blank=True)
    destination = models.CharField(max_length=150, blank=True)
    visa_type = models.CharField(max_length=150, blank=True)
    summary = models.TextField(blank=True)
    lead_score = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    qualified_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated"]

    def __str__(self):
        return f"{self.name or self.email or 'Visitor'} ({self.get_status_display()}, score {self.lead_score})"

    @property
    def is_qualified(self):
        return self.status in (self.Status.QUALIFIED, self.Status.HANDED_OFF)


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Visitor"
        ASSISTANT = "assistant", "AI"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created", "id"]

    def __str__(self):
        return f"{self.role}: {self.content[:60]}"


class InboundEmail(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DRAFT = "draft", "Draft (awaiting approval)"
        REPLIED = "replied", "Replied"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    message_id = models.CharField(max_length=255, unique=True)
    sender = models.EmailField()
    sender_name = models.CharField(max_length=150, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    skip_reason = models.CharField(max_length=200, blank=True)
    reply_text = models.TextField(blank=True, help_text="You can edit a draft before approving it.")
    error = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    session = models.ForeignKey(ChatSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    received_at = models.DateTimeField(auto_now_add=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.sender}: {self.subject[:50]}"

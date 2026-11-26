import uuid
from django.conf import settings
from django.db import models

class ConversationSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    learner = models.ForeignKey('directory.LearnerProfile', on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='active')
    turns = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ConversationMessage(models.Model):
    session = models.ForeignKey(ConversationSession, related_name='messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=12)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['pk']

class ConsultationDraft(models.Model):
    session = models.OneToOneField(ConversationSession, related_name='draft', on_delete=models.CASCADE)
    data = models.JSONField(default=dict)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    final_result = models.JSONField(null=True, blank=True)

import uuid
from django.conf import settings
from django.db import models


class ImportBatch(models.Model):
    class Dataset(models.TextChoices):
        QUALIFICATIONS = "qualifications", "Qualifications"
        MODULES = "modules", "Modules"
        CURRICULUM = "curriculum", "Curriculum"
        TOPICS = "topics", "Topics"
        FACULTY = "faculty", "Faculty"
        LEARNERS = "learners", "Learners"

    class State(models.TextChoices):
        PREVIEWED = "previewed", "Previewed"
        INVALID = "invalid", "Invalid"
        CONFIRMED = "confirmed", "Confirmed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.CharField(max_length=14, choices=Dataset.choices)
    source_filename = models.CharField(max_length=255)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PREVIEWED)
    records = models.JSONField(default=list)
    errors = models.JSONField(default=list, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    unchanged_count = models.PositiveIntegerField(default=0)
    preview_digest = models.CharField(max_length=64, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.dataset} import {self.id} ({self.state})"

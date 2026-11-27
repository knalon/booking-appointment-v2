from django.conf import settings
from django.db import models


class CoordinatorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='coordinator_profile')
    full_name = models.CharField(max_length=160)
    role = models.CharField(max_length=24, choices=[('coordinator','Coordinator'),('programme_manager','Programme Manager')], default='coordinator')
    qualifications = models.ManyToManyField('directory.Qualification', related_name='coordinator_profiles')
    active = models.BooleanField(default=True)


class ReviewCase(models.Model):
    draft = models.OneToOneField('nlp.ConsultationDraft', on_delete=models.PROTECT, related_name='review_case')
    qualification = models.ForeignKey('directory.Qualification', on_delete=models.PROTECT, null=True)
    assigned_to = models.ForeignKey(CoordinatorProfile, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=16, choices=[('open','Open'),('in_review','In review'),('escalated','Escalated'),('resolved','Resolved')], default='open')
    reason = models.CharField(max_length=40)
    trigger_key = models.CharField(max_length=100)
    urgent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-urgent','-updated_at','-pk']


class ReviewEvent(models.Model):
    case = models.ForeignKey(ReviewCase, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=32)
    detail = models.CharField(max_length=1000, blank=True)
    learner_visible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['pk']

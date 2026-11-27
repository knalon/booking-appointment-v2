from django.db import models
from django.conf import settings

class FacultyWindow(models.Model):
    faculty = models.ForeignKey('directory.FacultyProfile', on_delete=models.PROTECT)
    start = models.DateTimeField()
    end = models.DateTimeField()
    kind = models.CharField(max_length=12, choices=[('available','Available'),('busy','Busy')])
    mode = models.CharField(max_length=16, default='either')
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta:
        ordering = ['start','pk']

class ScheduleRun(models.Model):
    draft = models.ForeignKey('nlp.ConsultationDraft',on_delete=models.PROTECT,related_name='schedule_runs')
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(default=dict)
    class Meta:
        ordering = ['-pk']

class SlotSelection(models.Model):
    draft = models.OneToOneField('nlp.ConsultationDraft',on_delete=models.PROTECT,related_name='slot_selection')
    run = models.ForeignKey(ScheduleRun,on_delete=models.PROTECT)
    faculty = models.ForeignKey('directory.FacultyProfile',on_delete=models.PROTECT)
    start = models.DateTimeField()
    end = models.DateTimeField()
    mode = models.CharField(max_length=16)
    updated_at = models.DateTimeField(auto_now=True)

class Appointment(models.Model):
    draft = models.ForeignKey('nlp.ConsultationDraft', on_delete=models.PROTECT, related_name='appointments')
    faculty = models.ForeignKey('directory.FacultyProfile', on_delete=models.PROTECT)
    start = models.DateTimeField()
    end = models.DateTimeField()
    mode = models.CharField(max_length=16)
    status = models.CharField(max_length=24, default='pending')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-pk']
        indexes = [models.Index(fields=['faculty','start','end'], name='appt_faculty_time_idx')]

class AppointmentEvent(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=32)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointment, on_delete=models.PROTECT, null=True, blank=True)
    review_case = models.ForeignKey('coordinator.ReviewCase', on_delete=models.PROTECT, null=True, blank=True)
    message = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-pk']
        indexes = [models.Index(fields=['recipient','read_at'], name='notification_unread_idx')]
        constraints = [models.CheckConstraint(condition=(models.Q(appointment__isnull=False, review_case__isnull=True) | models.Q(appointment__isnull=True, review_case__isnull=False)), name='notification_one_target')]

class TeamsMeeting(models.Model):
    appointment = models.OneToOneField(Appointment,on_delete=models.PROTECT,related_name='teams_meeting')
    status = models.CharField(max_length=24,default='queued')
    event_id = models.TextField(blank=True)
    join_url = models.TextField(blank=True)
    requested_start = models.DateTimeField(null=True)
    requested_end = models.DateTimeField(null=True)
    detail = models.CharField(max_length=250,blank=True)
    test_mode = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

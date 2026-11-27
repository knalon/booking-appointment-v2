"""Creation-only integration. No automatic retry after ambiguous remote outcomes."""
import json
from datetime import timezone as utc_timezone
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from django.conf import settings
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from .models import Appointment, TeamsMeeting, Notification

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def enabled(): return settings.TEAMS_INTEGRATION_ENABLED

def on_transition(a):
    # Called inside booking transaction, including expiry. Never calls network.
    row=TeamsMeeting.objects.filter(appointment=a).first()
    if row:
        if a.status in ('cancelled','declined','expired','reschedule_requested') or (a.status=='confirmed' and row.requested_start and (row.requested_start!=a.start or row.requested_end!=a.end)):
            if row.status in ('queued','blocked'):
                row.status='queued' if a.status=='confirmed' else 'withdrawn'
            else:
                row.status='review_required'
            row.detail='Appointment changed; check organiser calendar before any further action.'
            row.save()
        elif a.status=='confirmed' and row.status=='withdrawn':
            row.status='queued';row.detail='';row.save()
    elif enabled() and a.status=='confirmed' and a.mode=='online' and a.start>timezone.now():
        TeamsMeeting.objects.create(appointment=a,test_mode=settings.TEAMS_TEST_MODE)

def payload(a):
    if settings.TEAMS_TEST_MODE:
        if not settings.DEBUG: raise ValueError('Test mode requires DEBUG=True.')
        emails=[settings.TEAMS_TEST_FACULTY_EMAIL,settings.TEAMS_TEST_LEARNER_EMAIL]
    else:
        emails=[a.faculty.email,a.draft.session.learner.email]
    emails=[e.strip() for e in emails]
    allowed={e.strip().lower() for e in settings.TEAMS_ALLOWED_EMAILS.split(',') if e.strip()}
    for e in emails:
        validate_email(e)
        if settings.TEAMS_TEST_MODE and e.lower() not in allowed: raise ValueError('Recipient not allowlisted.')
    if emails[0].lower()==emails[1].lower(): raise ValueError('Use two distinct recipients.')
    if not settings.TEAMS_TEST_MODE:
        domains={d.strip().lower() for d in settings.TEAMS_REGISTERED_EMAIL_DOMAINS.split(',') if d.strip()}
        if domains and any(e.rsplit('@',1)[1].lower() not in domains for e in emails):
            raise ValueError('Registered recipient domain not approved.')
    fmt=lambda d:d.astimezone(utc_timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return dict(appointment_id=f'APT-{a.pk}',subject=('TEST - ' if settings.TEAMS_TEST_MODE else '')+f'Academic Consultation APT-{a.pk}',start_time=fmt(a.start),end_time=fmt(a.end),faculty_email=emails[0],learner_email=emails[1])

def endpoint():
    url=settings.POWER_AUTOMATE_MEETING_URL.strip();p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment or not (p.hostname.endswith('.environment.api.powerplatform.com') or p.hostname.endswith('.logic.azure.com')) or not parse_qs(p.query).get('sig'):
        raise ValueError('Configure an approved HTTPS signed Power Automate endpoint.')
    return url

def create_remote(url,data):
    req=Request(url,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'},method='POST')
    with build_opener(NoRedirect()).open(req,timeout=90) as response:
        if response.status!=200: raise ValueError('Unexpected HTTP status')
        result=json.loads(response.read(65537))
    if result.get('success') is not True or result.get('appointment_id')!=data['appointment_id']: raise ValueError('Invalid response')
    event=result.get('event_id');join=result.get('join_url')
    if not isinstance(event,str) or not event.strip() or len(event)>4096 or not isinstance(join,str) or len(join)>8192: raise ValueError('Missing meeting information')
    p=urlsplit(join)
    if p.scheme!='https' or p.hostname!='teams.microsoft.com' or p.username or p.password or not p.path.startswith(('/l/meetup-join/','/meet/')): raise ValueError('Invalid meeting link')
    return event,join

def process_one():
    if not enabled(): return False
    pk=TeamsMeeting.objects.filter(status='queued').order_by('pk').values_list('appointment_id',flat=True).first()
    if pk is None: return False
    with transaction.atomic():
        a=Appointment.objects.select_for_update().get(pk=pk)
        row=TeamsMeeting.objects.select_for_update().get(appointment=a)
        if row.status!='queued': return True
        if a.status!='confirmed' or a.mode!='online' or a.start<=timezone.now():
            row.status='withdrawn';row.save();return True
        try:
            if row.test_mode != settings.TEAMS_TEST_MODE: raise ValueError("Queued mode differs from current configuration.")
            url=endpoint();data=payload(a)
        except Exception:
            row.status='blocked';row.detail='Check endpoint and approved recipient configuration. No request sent.';row.save();return True
        row.status='sending';row.requested_start=a.start;row.requested_end=a.end;row.test_mode=settings.TEAMS_TEST_MODE;row.detail='';row.save()
    # Persist claim before sending. A crash leaves sending for manual investigation.
    try: event,join=create_remote(url,data)
    except Exception:
        with transaction.atomic():
            a=Appointment.objects.select_for_update().get(pk=pk);row=TeamsMeeting.objects.select_for_update().get(appointment=a)
            row.status='review_required';row.detail='Remote outcome uncertain. Check flow history; do not resend automatically.';row.save()
        return True
    with transaction.atomic():
        a=Appointment.objects.select_for_update().get(pk=pk);row=TeamsMeeting.objects.select_for_update().get(appointment=a)
        row.event_id=event;row.join_url=join
        if row.status=='sending' and a.status=='confirmed' and a.start==row.requested_start and a.end==row.requested_end:
            row.status='ready';row.detail=''
            for uid in {a.faculty.user_id,a.draft.session.owner_id}:
                if uid: Notification.objects.create(recipient_id=uid,appointment=a,message='Teams test meeting ready. Invitations sent to configured test recipients.' if row.test_mode else 'Microsoft Teams meeting ready.')
        else:
            row.status='review_required';row.detail='Meeting created but appointment changed. Reconcile organiser calendar manually.'
        row.save()
    return True

def public_status(a,user):
    row=TeamsMeeting.objects.filter(appointment=a).first()
    if not row: return None
    allowed=user.is_staff or user.pk in (a.faculty.user_id,a.draft.session.owner_id)
    return {'status':row.status,'test_mode':row.test_mode,'detail':row.detail,'join_url':row.join_url if allowed and row.status=='ready' and a.status=='confirmed' and a.start==row.requested_start and a.end==row.requested_end else ''}

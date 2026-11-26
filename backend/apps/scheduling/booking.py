"""Transactional appointment workflow. Every writer locks learner then faculty.
Availability writers already lock faculty. Pending holds expire at the earlier
of 24 hours after submission and the appointment start.
"""
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.directory.models import FacultyProfile, LearnerProfile
from apps.nlp.models import ConsultationDraft
from apps.matching.services import active_policy, calculate
from apps.matching.eligibility import key
from .models import Appointment, AppointmentEvent, Notification, FacultyWindow, SlotSelection
from .slots import within_working_hours
from .faculty_access import faculty_for

HELD = ('pending','reschedule_requested')
ACTIVE = (*HELD,'confirmed')

def active_holds(now=None):
    now=now or timezone.now()
    return Appointment.objects.filter(Q(status='confirmed')|Q(status__in=HELD,expires_at__gt=now),end__gt=now)

def conflicts(start,end,faculty=None,learner=None,exclude=None):
    rows=active_holds().filter(start__lt=end,end__gt=start)
    if exclude: rows=rows.exclude(pk=exclude)
    condition=Q()
    if faculty is not None: condition |= Q(faculty_id=faculty)
    if learner is not None: condition |= Q(draft__session__learner_id=learner)
    return rows.filter(condition)

def notify(a,recipient,message):
    if recipient: Notification.objects.create(appointment=a,recipient_id=recipient,message=message)

def event(a,actor,action,detail=None):
    AppointmentEvent.objects.create(appointment=a,actor=actor,action=action,detail=detail or {})

def lock_participants(draft,faculty_id):
    learner=LearnerProfile.objects.select_for_update().get(pk=draft.session.learner_id)
    faculty=FacultyProfile.objects.select_for_update().get(pk=faculty_id)
    return learner,faculty

def check_slot(draft,learner,faculty,start,end,mode,exclude=None):
    now=timezone.now()
    if start<=now or end-start!=timedelta(minutes=30) or start>now+timedelta(days=30):
        raise ValidationError('Choose a future 30-minute slot within 30 days.')
    if learner.status!='Active' or learner.user_id!=draft.session.owner_id or not learner.user.is_active or faculty.status!='Active' or not faculty.user_id or faculty_for(faculty.user) is None:
        raise ValidationError('An active learner and faculty account are required.')
    row,policy=active_policy(); result=calculate(draft,policy,row.pk if row else 'original-v1')
    candidate=next((c for c in result['candidates'] if c['faculty_id']==faculty.faculty_id),None)
    if not candidate or candidate['academic_band']=='Review': raise ValidationError('Faculty no longer meets academic eligibility policy.')
    requested=key(draft.final_result['request'].get('mode'))
    if mode not in {'online','facetoface'} or mode not in {key(x) for x in faculty.consultation_modes} or requested not in (mode,'either'):
        raise ValidationError('Incompatible consultation mode.')
    if not within_working_hours(faculty,start,end): raise ValidationError('Outside faculty working hours.')
    if not FacultyWindow.objects.filter(faculty=faculty,active=True,kind='available',start__lte=start,end__gte=end,mode__in=[mode,'either']).exists():
        raise ValidationError('Slot is no longer published.')
    if FacultyWindow.objects.filter(faculty=faculty,active=True,kind='busy',start__lt=end,end__gt=start).exists() or conflicts(start,end,faculty.pk,learner.pk,exclude).exists():
        raise ValidationError('This time overlaps an existing commitment or appointment. Refresh availability.')

def deadline(start): return min(start,timezone.now()+timedelta(hours=24))

def expire(a):
    if a.status in HELD and a.expires_at<=timezone.now():
        a.status='expired';a.save(update_fields=['status','updated_at']);event(a,None,'expired')
        notify(a,a.draft.session.owner_id,'Appointment request expired. You may select another time.')
        notify(a,a.faculty.user_id,'An appointment request expired and its slot was released.')
        return True
    return False

@transaction.atomic
def submit(draft_id,user,selection):
    draft=ConsultationDraft.objects.select_for_update().get(pk=draft_id)
    if draft.session.owner_id!=user.pk or draft.session.status!='confirmed': raise PermissionDenied()
    existing=active_holds().filter(draft=draft).first()
    if existing: return existing,False
    s=SlotSelection.objects.filter(draft=draft).first()
    if not s or s.run.draft_id!=draft.pk: raise ValidationError('Select a faculty member and time first.')
    if not isinstance(selection,dict) or any(selection.get(k)!=v for k,v in {'run_id':s.run_id,'faculty_id':s.faculty.faculty_id,'mode':s.mode}.items()) or selection.get('start')!=s.start.isoformat() or selection.get('end')!=s.end.isoformat():
        raise ValidationError('Selection has changed. Refresh and review it again.')
    learner,faculty=lock_participants(draft,s.faculty_id)
    check_slot(draft,learner,faculty,s.start,s.end,s.mode)
    a=Appointment.objects.create(draft=draft,faculty=faculty,start=s.start,end=s.end,mode=s.mode,expires_at=deadline(s.start))
    event(a,user,'submitted');notify(a,faculty.user_id,'New consultation request awaiting your approval.');notify(a,user.pk,'Appointment request submitted. Awaiting faculty approval.')
    return a,True

@transaction.atomic
def transition(pk,user,action,data):
    initial=Appointment.objects.get(pk=pk)
    draft=ConsultationDraft.objects.select_for_update().get(pk=initial.draft_id)
    learner,faculty=lock_participants(draft,initial.faculty_id)
    a=Appointment.objects.select_for_update().get(pk=pk)
    is_learner=user.pk==draft.session.owner_id and not user.is_staff
    is_faculty=user.pk==faculty.user_id and not user.is_staff
    if not (is_learner or is_faculty or user.is_staff): raise PermissionDenied()
    if expire(a): return a
    before={'status':a.status,'start':a.start.isoformat(),'end':a.end.isoformat()}
    reason=data.get('reason','')
    if not isinstance(reason,str) or len(reason)>500: raise ValidationError('Reason must be at most 500 characters.')
    if action=='accept' and ((is_faculty and a.status=='pending') or (is_learner and a.status=='reschedule_requested')):
        check_slot(draft,learner,faculty,a.start,a.end,a.mode,a.pk);a.status='confirmed';a.expires_at=None
    elif action=='decline' and ((is_faculty and a.status=='pending') or (is_learner and a.status=='reschedule_requested')):
        a.status='declined';a.expires_at=None
    elif action=='cancel' and a.status in ACTIVE and a.start>timezone.now():
        a.status='cancelled';a.expires_at=None
    elif action=='propose' and is_faculty and a.status in ('pending','confirmed') and a.start>timezone.now():
        from .slots import local_time
        try: start=local_time(data['start'],faculty.time_zone)
        except (KeyError,ValueError,TypeError): raise ValidationError('Choose a valid local date and time.') from None
        end=start+timedelta(minutes=30)
        check_slot(draft,learner,faculty,start,end,a.mode,a.pk)
        a.start=start;a.end=end;a.status='reschedule_requested';a.expires_at=deadline(start)
    elif action in ('complete','no_show') and (is_faculty or user.is_staff) and a.status=='confirmed' and a.end<=timezone.now():
        a.status='completed' if action=='complete' else 'no_show'
    else: raise ValidationError('This action is not permitted for the current appointment state.')
    a.save();event(a,user,action,{'previous':before,'reason':reason,'status':a.status,'start':a.start.isoformat(),'end':a.end.isoformat()})
    message={'confirmed':'Appointment confirmed.','declined':'Appointment declined. You may choose another time.','cancelled':'Appointment cancelled.','reschedule_requested':'Faculty proposed a different time. Review the appointment.','completed':'Consultation marked completed.','no_show':'Consultation marked no-show.'}[a.status]
    for uid in {draft.session.owner_id,faculty.user_id}:
        if uid!=user.pk: notify(a,uid,message)
    return a

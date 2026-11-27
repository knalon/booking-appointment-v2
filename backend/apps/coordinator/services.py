"""Case workflow; does not change confirmed snapshots or appointments."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.directory.models import Qualification
from apps.nlp.models import ConsultationDraft
from apps.scheduling.models import Notification
from apps.scheduling.booking import active_holds
from apps.matching.services import active_policy, calculate
from .models import CoordinatorProfile, ReviewCase, ReviewEvent
from .access import profile_for, scoped_cases

REASONS = {'urgent':'Urgent consultation','support_review':'Institutional technical support','coordinator_review':'Administrative or unresolved consultation','academic_review':'No suitable academic match','no_slots':'No compatible faculty slots','appointment_declined':'Appointment declined','appointment_expired':'Appointment expired','learner_requested':'Learner requested assistance'}


def record(case, actor, action, detail='', public=False):
    ReviewEvent.objects.create(case=case,actor=actor,action=action,detail=detail,learner_visible=public)


def notify(case, uid, message):
    if uid: Notification.objects.create(review_case=case,recipient_id=uid,message=message[:250])


def team_ids(case, role='coordinator'):
    if not case.qualification_id or case.draft.session.learner.qualification_id!=case.qualification_id or not case.qualification.is_active:
        return []
    profiles=CoordinatorProfile.objects.filter(active=True,role=role,qualifications=case.qualification,user__is_active=True,user__is_staff=False,user__is_superuser=False).exclude(user__faculty_profile__isnull=False).exclude(user__learner_profile__isnull=False)
    return list(profiles.values_list('user_id',flat=True).distinct())


def alert_team(case, message, role='coordinator'):
    ids=team_ids(case,role)
    # Admin is the fallback for unassigned qualifications, and escalation oversight.
    if not ids or role=='programme_manager':
        ids += list(get_user_model().objects.filter(is_active=True,is_superuser=True,is_staff=True).values_list('pk',flat=True))
    for uid in set(ids): notify(case,uid,message)


def detect(draft):
    final=draft.final_result or {}; req=final.get('request') or {}
    route=final.get('routing'); urgent=req.get('urgency')=='urgent'
    if route in ('support_review','coordinator_review'): return route,route,urgent
    if req.get('consultation_type')=='other': return 'coordinator_review','coordinator_review',urgent
    # Historical technical records lack reliable scope; matching will review them.
    if req.get('consultation_type')=='technical' and final.get('schema_version') not in ('1.2','1.3'):
        return 'coordinator_review','coordinator_review',urgent
    held=active_holds().filter(draft=draft).first()
    if held and held.status=='confirmed': return None
    latest=draft.appointments.first()
    if latest and latest.status in ('completed','no_show'): return None
    if not held and latest:
        if latest.status=='declined': return 'appointment_declined',f'declined:{latest.pk}',urgent
        if latest.status=='expired' or (latest.status in ('pending','reschedule_requested') and latest.expires_at and latest.expires_at<=timezone.now()):
            return 'appointment_expired',f'expired:{latest.pk}',urgent
    if not held:
        run=draft.schedule_runs.first(); recommendation=draft.recommendations.first()
        if run and run.result.get('status')=='needs_review': return 'academic_review','academic_review',urgent
        if run and run.result.get('status')=='no_slots': return 'no_slots','no_slots',urgent
        if not run and recommendation and recommendation.result.get('status')=='needs_review': return 'academic_review','academic_review',urgent
    if urgent: return 'urgent','urgent',True
    return None


@transaction.atomic
def sync_case(draft_id, explicit=False, actor=None):
    draft=ConsultationDraft.objects.select_for_update().get(pk=draft_id)
    if not draft.final_result or draft.session.status!='confirmed': return None
    case=ReviewCase.objects.select_for_update().filter(draft=draft).first()
    trigger=('learner_requested','learner_requested',draft.final_result.get('request',{}).get('urgency')=='urgent') if explicit else detect(draft)
    if not trigger: return case
    reason,key,urgent=trigger
    if case and case.status!='resolved' and not explicit:
        # Keep escalation, ownership and original reason; append new distinct system signals.
        if key!=case.trigger_key and key!='urgent':
            case.reason=reason;case.trigger_key=key;case.urgent=urgent;case.save(update_fields=['reason','trigger_key','urgent','updated_at']);record(case,None,'signal_updated',REASONS[reason])
        return case
    if case and case.status!='resolved': return case
    if case and case.trigger_key==key and not explicit: return case
    q=Qualification.objects.filter(code=draft.final_result.get('qualification_code')).first()
    if case:
        case.status='open';case.assigned_to=None;case.reason=reason;case.trigger_key=key;case.urgent=urgent;case.save();record(case,actor,'reopened',REASONS[reason],explicit)
    else:
        case=ReviewCase.objects.create(draft=draft,qualification=q,reason=reason,trigger_key=key,urgent=urgent);record(case,actor,'opened',REASONS[reason],explicit)
    alert_team(case,'New consultation review requires attention.')
    return case


def eligible_candidates(case):
    row,policy=active_policy(); result=calculate(case.draft,policy,row.pk if row else 'original-v1')
    return [{k:c[k] for k in ('faculty_id','name','expertise_level','academic_band','academic_score')} for c in result['candidates'] if c['academic_band']!='Review']


@transaction.atomic
def act(case_id,user,action,data):
    case=scoped_cases(user).filter(pk=case_id).first()
    if not case: raise PermissionDenied('Case not in your assigned scope.')
    # Lock draft before case, matching scheduling / intake writers.
    ConsultationDraft.objects.select_for_update().get(pk=case.draft_id)
    if not scoped_cases(user).filter(pk=case_id).exists(): raise PermissionDenied('Case scope changed.')
    case=ReviewCase.objects.select_for_update().get(pk=case_id)
    p=profile_for(user); staff=user.is_staff
    if not staff and not p: raise PermissionDenied()
    if case.status=='resolved' and action!='reopen': raise ValidationError('Case is resolved.')
    if case.status=='escalated' and not staff and p.role!='programme_manager': raise PermissionDenied('Programme Manager review required.')
    if not staff and p.role=='programme_manager' and case.status!='escalated' and action!='reopen': raise PermissionDenied('Programme Managers act on escalated cases only.')
    note=data.get('note','')
    if not isinstance(note,str) or len(note)>1000: raise ValidationError('Note must contain at most 1000 characters.')
    note=note.strip(); public=False
    if action=='claim':
        if not p or case.status not in ('open','in_review') or (case.assigned_to_id and case.assigned_to_id!=p.pk and case.assigned_to.active and case.qualification_id in case.assigned_to.qualifications.filter(is_active=True).values_list('pk',flat=True)):
            raise ValidationError('Case is already assigned or cannot be claimed.')
        case.assigned_to=p;case.status='in_review'
    elif action=='release':
        if case.status!='in_review' or (not staff and case.assigned_to_id!=p.pk): raise PermissionDenied('Only the assignee or management can release this case.')
        case.assigned_to=None;case.status='open'
    elif action=='reopen':
        if case.status!='resolved' or not note or (not staff and p.role!='coordinator'): raise ValidationError('Provide a reason to reopen a resolved case.')
        case.status='open';case.assigned_to=None
    else:
        if not staff and p.role=='coordinator' and case.assigned_to_id!=p.pk: raise PermissionDenied('Claim this case before taking action.')
        if action=='note':
            if not note: raise ValidationError('Enter an internal note.')
        elif action=='message':
            if not note: raise ValidationError('Enter a learner-facing message.')
            public=True
        elif action=='suggest':
            candidate=next((c for c in eligible_candidates(case) if c['faculty_id']==data.get('faculty_id')),None)
            if not candidate: raise ValidationError('Choose a faculty member who meets current academic eligibility and threshold.')
            note=f"Suggested faculty: {candidate['name']} ({candidate['faculty_id']}). Academic suitability verified; availability and booking are not guaranteed. Refresh availability in your consultation." + (' '+note if note else '')
            if len(note)>1000: raise ValidationError('Shorten the accompanying note.')
            public=True
        elif action=='escalate':
            if case.status not in ('open','in_review') or not note: raise ValidationError('Provide an escalation reason for an open case.')
            case.status='escalated';case.assigned_to=None
        elif action=='resolve':
            if not note: raise ValidationError('Provide a learner-facing resolution summary.')
            case.status='resolved';public=True
        else: raise ValidationError('Unknown review action.')
    case.save();record(case,user,action,note,public)
    if public: notify(case,case.draft.session.owner_id,'A consultation review has been updated. Open your review messages.')
    if action=='escalate': alert_team(case,'A consultation case has been escalated to Programme Manager review.','programme_manager')
    if action in ('release','reopen'): alert_team(case,'A consultation case is available for review.')
    return case

import json
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from apps.directory.models import Qualification, LearnerProfile
from apps.nlp.models import ConsultationDraft
from apps.scheduling.booking_views import serialize as appointment_json
from .access import profile_for, scope_codes, scoped_cases, scoped_appointments
from .models import CoordinatorProfile, ReviewCase
from .services import REASONS, sync_case, act, eligible_candidates


@csrf_protect
@require_POST
def sign_in(request):
    try:
        data=json.loads(request.body);user=authenticate(request,username=data['username'],password=data['password'])
    except (ValueError,KeyError,TypeError): return JsonResponse({'detail':'Invalid login request.'},status=400)
    if not user or not profile_for(user): return JsonResponse({'detail':'Invalid credentials or coordinator access not granted.'},status=403)
    login(request,user)
    return JsonResponse({'csrfToken':get_token(request)})


def require_team(user):
    if not user.is_staff and not profile_for(user): raise PermissionDenied('Coordinator access required.')


def profile_json(p):
    return {'id':p.pk,'username':p.user.get_username(),'full_name':p.full_name,'role':p.role,'active':p.active,'qualifications':list(p.qualifications.order_by('code').values_list('code',flat=True))}


class Session(APIView):
    def get(self,request):
        p=profile_for(request.user)
        if not p: raise PermissionDenied('Coordinator access required.')
        return Response({**profile_json(p),'csrfToken':get_token(request)})


class Accounts(APIView):
    def check(self,request):
        if not request.user.is_superuser or not request.user.is_staff: raise PermissionDenied('Superuser access required.')
    def get(self,request):
        self.check(request)
        return Response({'accounts':[profile_json(p) for p in CoordinatorProfile.objects.select_related('user').order_by('full_name')], 'qualifications':list(Qualification.objects.filter(is_active=True).order_by('code').values('code','name'))})
    @transaction.atomic
    def post(self,request):
        self.check(request); d=request.data
        p=None
        if 'id' in d: p=get_object_or_404(CoordinatorProfile.objects.select_for_update(),pk=d['id'])
        name=d.get('full_name'); role=d.get('role'); codes=d.get('qualifications'); active=d.get('active',True)
        if not isinstance(name,str) or not name.strip() or len(name)>160 or role not in ('coordinator','programme_manager') or type(active) is not bool or not isinstance(codes,list) or (active and not codes) or any(not isinstance(c,str) for c in codes): raise ValidationError('Provide name, role, active status and at least one qualification.')
        qualifications=list(Qualification.objects.filter(code__in=codes,is_active=True))
        if len(qualifications)!=len(set(codes)): raise ValidationError('Choose active qualifications only.')
        if p is None:
            username=d.get('username'); password=d.get('password')
            if not isinstance(username,str) or not username.strip() or len(username)>150 or not isinstance(password,str): raise ValidationError('Provide username and password.')
            U=get_user_model(); user=U(username=username.strip(),is_staff=False,is_superuser=False)
            try:
                user.full_clean(exclude=['password']);validate_password(password,user)
            except DjangoValidationError as e: raise ValidationError(e.messages) from None
            if U.objects.filter(username__iexact=user.username).exists(): raise ValidationError('Username already exists.')
            user.set_password(password)
            try:
                with transaction.atomic(): user.save()
            except IntegrityError: raise ValidationError('Username already exists.') from None
            p=CoordinatorProfile.objects.create(user=user,full_name=name.strip(),role=role,active=active)
        else:
            if p.user.is_staff or p.user.is_superuser or hasattr(p.user,'faculty_profile') or hasattr(p.user,'learner_profile'): raise ValidationError('Conflicting account role; cannot edit.')
            p.full_name=name.strip();p.role=role;p.active=active;p.save()
        p.qualifications.set(qualifications)
        # Remove stale ownership when permissions are revoked; preserve case history.
        from .services import record
        for case in ReviewCase.objects.filter(assigned_to=p,status='in_review').exclude(qualification__in=qualifications if active and role=='coordinator' else []):
            case.assigned_to=None;case.status='open';case.save();record(case,request.user,'assignment_released','Account scope changed.')
        return Response(profile_json(p),status=200 if 'id' in d else 201)


def case_json(c, learner=False, detail=False):
    final=c.draft.final_result or {}; req=final.get('request',{}); s=c.draft.session
    data={'id':c.pk,'request_id':str(s.pk),'qualification':c.qualification.code if c.qualification else final.get('qualification_code'),'status':c.status,'reason':REASONS.get(c.reason,c.reason),'urgent':c.urgent,'module':req.get('module_code'),'difficulty':req.get('difficulty'),'updated_at':c.updated_at,'assigned_to':c.assigned_to.full_name if c.assigned_to else None}
    if not learner: data.update(learner_name=s.learner.full_name,learner_id=s.learner.learner_id,assigned_id=c.assigned_to_id,consultation_type=req.get('consultation_type'),scope=req.get('consultation_scope'),preferred_date=req.get('preferred_date'),preferred_time=req.get('preferred_time'),urgency_reason=req.get('urgency_reason'))
    if detail or learner:
        events=c.events.all()
        if learner: events=events.filter(learner_visible=True)
        data['events']=[{'action':e.action,'detail':e.detail,'created_at':e.created_at,**({} if learner else {'actor':e.actor.get_username() if e.actor else 'System','learner_visible':e.learner_visible})} for e in events.select_related('actor')]
    if detail and not learner:
        data['candidates']=eligible_candidates(c) if c.status!='resolved' else []
        latest=c.draft.appointments.first(); run=c.draft.schedule_runs.first()
        data['latest_appointment_status']=latest.status if latest else None
        data['latest_scheduling_status']=run.result.get('status') if run else None
        data['current_qualification']=s.learner.qualification.code if s.learner.qualification else None
    return data


class Cases(APIView):
    def get(self,request):
        require_team(request.user);qs=scoped_cases(request.user)
        status=request.query_params.get('status','active')
        if status=='active': qs=qs.exclude(status='resolved')
        elif status!='all': qs=qs.filter(status=status)
        return Response({'counts':{'open':scoped_cases(request.user).filter(status='open').count(),'urgent':scoped_cases(request.user).exclude(status='resolved').filter(urgent=True).count(),'escalated':scoped_cases(request.user).filter(status='escalated').count(),'resolved':scoped_cases(request.user).filter(status='resolved').count()},'cases':[case_json(c) for c in qs[:200]]})
    def post(self,request):
        # Explicit backfill of historical confirmed consultations, not a side effect of reading.
        require_team(request.user);qs=ConsultationDraft.objects.filter(session__status='confirmed',final_result__isnull=False)
        p=profile_for(request.user)
        if not request.user.is_staff:
            from django.db.models import F
            from django.db.models.fields.json import KeyTextTransform
            qs=qs.annotate(confirmed_qualification=KeyTextTransform('qualification_code','final_result')).filter(session__learner__qualification__code__in=scope_codes(p),confirmed_qualification=F('session__learner__qualification__code'))
        ids=list(qs.order_by('-confirmed_at','-pk').values_list('pk',flat=True)[:200]);
        for pk in ids: sync_case(pk)
        return Response({'reviewed':len(ids)})


class CaseDetail(APIView):
    def get(self,request,pk):
        require_team(request.user);return Response(case_json(get_object_or_404(scoped_cases(request.user),pk=pk),detail=True))
    def post(self,request,pk):
        require_team(request.user);get_object_or_404(scoped_cases(request.user),pk=pk)
        act(pk,request.user,request.data.get('action'),request.data)
        return self.get(request,pk)


class LearnerCases(APIView):
    def scope(self,user):
        if user.is_staff or not LearnerProfile.objects.filter(user=user,status='Active').exists(): raise PermissionDenied('Learner access required.')
        return ReviewCase.objects.filter(draft__session__owner=user,draft__session__learner__user=user).select_related('draft__session','qualification','assigned_to')
    def get(self,request): return Response([case_json(c,learner=True) for c in self.scope(request.user)[:100]])
    def post(self,request):
        self.scope(request.user)
        try: draft=get_object_or_404(ConsultationDraft.objects.filter(session__owner=request.user,session__learner__user=request.user,session__status='confirmed',final_result__isnull=False),session_id=request.data.get('request_id'))
        except (DjangoValidationError,ValueError,TypeError): raise ValidationError('Invalid consultation ID.') from None
        c=sync_case(draft.pk,explicit=True,actor=request.user)
        return Response(case_json(c,learner=True))


class Appointments(APIView):
    def get(self,request):
        require_team(request.user)
        # Read-only; do not delegate booking approval or cancellation privileges.
        rows=scoped_appointments(request.user)
        now=timezone.now()
        return Response([{**appointment_json(a,request.user),'role':'coordinator','qualification':a.draft.final_result.get('qualification_code'),'time_zone':a.draft.session.learner.time_zone,'status':'expired' if a.status in ('pending','reschedule_requested') and a.expires_at and a.expires_at<=now else a.status} for a in rows[:100]])

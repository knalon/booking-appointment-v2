from datetime import timedelta, datetime
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from apps.directory.models import FacultyProfile
from apps.matching.views import Recommendation
from .models import FacultyWindow,ScheduleRun,SlotSelection
from .slots import local_time,within_working_hours
from .services import build, automatic_build
from apps.matching.services import create_run
from .faculty_access import faculty_for
from .booking import conflicts, active_holds
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError


def checked(fn):
    try: return fn()
    except (ValueError,TypeError,KeyError,ZoneInfoNotFoundError,OverflowError) as e: raise ValidationError(str(e)) from None

def window_json(w):
    z=ZoneInfo(w.faculty.time_zone)
    return {'id':w.pk,'faculty_id':w.faculty.faculty_id,'start':w.start.astimezone(z).isoformat(),'end':w.end.astimezone(z).isoformat(),'kind':w.kind,'mode':w.mode,'active':w.active}

class Availability(APIView):
    permission_classes=[IsAuthenticated]
    def scope(self,request):
        if request.user.is_staff: return FacultyProfile.objects.all()
        f=faculty_for(request.user)
        if f is None: raise PermissionDenied('Faculty or management access required.')
        return FacultyProfile.objects.filter(pk=f.pk)
    def get(self,request):
        scope=self.scope(request).filter(status='Active')
        faculty=list(scope.order_by('full_name').values('faculty_id','full_name','time_zone','working_days','working_hours_start','working_hours_end','consultation_modes'))
        fid=request.query_params.get('faculty')
        if not request.user.is_staff and not fid: fid=faculty[0]['faculty_id'] if faculty else None
        if fid and not scope.filter(faculty_id=fid).exists(): raise PermissionDenied('Faculty schedule access denied.')
        rows=FacultyWindow.objects.select_related('faculty').filter(faculty__in=scope,faculty__faculty_id=fid,end__gt=timezone.now()).order_by('start') if fid else FacultyWindow.objects.none()
        appointments=[]
        if fid:
            for a in active_holds().filter(faculty__in=scope,faculty__faculty_id=fid).select_related('faculty'):
                z=ZoneInfo(a.faculty.time_zone); appointments.append({'id':f'appointment-{a.pk}','start':a.start.astimezone(z).isoformat(),'end':a.end.astimezone(z).isoformat(),'kind':'appointment-confirmed' if a.status=='confirmed' else 'appointment-pending','mode':a.mode,'active':True})
        return Response({'faculty':faculty,'windows':[window_json(w) for w in rows],'appointments':appointments})
    def parse(self,f,data):
        a,b=local_time(data['start'],f.time_zone),local_time(data['end'],f.time_zone)
        kind=data.get('kind'); mode=data.get('mode','either'); now=timezone.now()
        if kind not in ('available','busy') or mode not in ('online','facetoface','either') or a>=b or a<now or b>now+timedelta(days=90) or b-a>timedelta(days=1): raise ValueError('Use valid future windows within 90 days, at most 24 hours.')
        if kind=='available' and not within_working_hours(f,a,b): raise ValueError('Availability must fall within faculty working days and hours.')
        if kind=='available':
            from apps.matching.eligibility import key
            supported={key(m) for m in f.consultation_modes}&{'online','facetoface'}
            if not supported or (mode!='either' and mode not in supported): raise ValueError('Faculty does not support this mode.')
        return a,b,kind,mode
    @transaction.atomic
    def post(self,request):
        data=request.data
        f=get_object_or_404(self.scope(request).select_for_update(),faculty_id=data.get('faculty_id'),status='Active')
        def parse_all():
            weeks=data.get('repeat_weeks',1)
            if type(weeks) is not int or not 1<=weeks<=12: raise ValueError('Repeat must be 1–12 weeks.')
            a,b=datetime.fromisoformat(data['start']),datetime.fromisoformat(data['end'])
            return [self.parse(f,{**data,'start':(a+timedelta(weeks=i)).isoformat(),'end':(b+timedelta(weeks=i)).isoformat()}) for i in range(weeks)]
        parsed=checked(parse_all); rows=[]
        for a,b,kind,mode in parsed:
            if kind=='busy' and conflicts(a,b,faculty=f.pk).exists(): raise ValidationError('Cancel or reschedule the overlapping appointment first.')
            if FacultyWindow.objects.filter(faculty=f,start=a,end=b,kind=kind,mode=mode,active=True).exists(): raise ValidationError('An identical active window already exists.')
            rows.append(FacultyWindow.objects.create(faculty=f,start=a,end=b,kind=kind,mode=mode,created_by=request.user))
        return Response(window_json(rows[0]) if len(rows)==1 else {'windows':[window_json(w) for w in rows]},status=201)
    @transaction.atomic
    def patch(self,request):
        scope=self.scope(request)
        target=get_object_or_404(FacultyWindow.objects.filter(faculty__in=scope,faculty__status='Active'),pk=request.data.get('id'))
        f=get_object_or_404(scope.select_for_update(),pk=target.faculty_id,status='Active')
        w=get_object_or_404(FacultyWindow.objects.select_for_update(),pk=target.pk,faculty=f)
        data=request.data
        if 'active' in data and type(data['active']) is not bool: raise ValidationError('Provide active as a boolean.')
        edit=any(k in data for k in ('start','end','kind','mode'))
        if not edit and 'active' not in data: raise ValidationError('No changes supplied.')
        active=data.get('active',w.active)
        if (edit or not active) and conflicts(w.start,w.end,faculty=f.pk).exists(): raise ValidationError('Cancel or reschedule the overlapping appointment before changing this window.')
        if edit or active:
            z=ZoneInfo(f.time_zone)
            values={'start':w.start.astimezone(z).replace(tzinfo=None).isoformat(),'end':w.end.astimezone(z).replace(tzinfo=None).isoformat(),'kind':w.kind,'mode':w.mode}
            values.update({k:data[k] for k in values if k in data})
            w.start,w.end,w.kind,w.mode=checked(lambda:self.parse(f,values))
            if active and w.kind=='busy' and conflicts(w.start,w.end,faculty=f.pk).exists(): raise ValidationError('Cancel or reschedule the overlapping appointment first.')
            if active and FacultyWindow.objects.filter(faculty=f,start=w.start,end=w.end,kind=w.kind,mode=w.mode,active=True).exclude(pk=w.pk).exists(): raise ValidationError('An identical active window already exists.')
        w.active=active;w.save(update_fields=['start','end','kind','mode','active']);return Response(window_json(w))


def selection_json(draft):
    s=SlotSelection.objects.filter(draft=draft).select_related('faculty').first()
    return None if not s else {'faculty_id':s.faculty.faculty_id,'name':s.faculty.full_name,'start':s.start.isoformat(),'end':s.end.isoformat(),'mode':s.mode,'status':'provisional_selection','run_id':s.run_id}

def payload(request,draft,run):
    result=None
    if run:
        result={**run.result,'run_id':run.pk}
        if not request.user.is_staff:
            result.pop('policy',None)
            safe=('faculty_id','name','department','expertise_level','languages','modes','teaching_years','currently_teaching','preferred_faculty_match','match_type','academic_band','final_band','availability_status','slots')
            by_id={c['faculty_id']:c for c in result['candidates']}
            result['candidates']=[{k:by_id[i][k] for k in safe} for i in result['display_ids']]
    appointment=active_holds().filter(draft=draft).first()
    return {'result':result,'selection':selection_json(draft),'request':draft.final_result['request'],'time_zone':draft.session.learner.time_zone,'appointment_status':appointment.status if appointment else None}

class Schedule(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request,pk):
        draft=Recommendation().draft(request,pk)
        return Response(payload(request,draft,draft.schedule_runs.first()))
    @transaction.atomic
    def post(self,request,pk):
        if request.user.is_staff: raise PermissionDenied('Only the learner may confirm their availability windows.')
        draft=Recommendation().draft(request,pk,True)
        # Reuse the persisted search unless the learner explicitly refreshes.
        previous=draft.schedule_runs.first()
        if active_holds().filter(draft=draft).exists(): return Response(payload(request,draft,previous))
        if previous and request.data.get('refresh') is not True:
            return Response(payload(request,draft,previous))
        if not draft.recommendations.exists(): create_run(draft)
        result=checked(lambda:automatic_build(draft));run=ScheduleRun.objects.create(draft=draft,result=result)
        SlotSelection.objects.filter(draft=draft).delete()
        return Response(payload(request,draft,run),status=201)
    @transaction.atomic
    def patch(self,request,pk):
        if request.user.is_staff: raise PermissionDenied('Only the learner may select a slot.')
        draft=Recommendation().draft(request,pk,True)
        if active_holds().filter(draft=draft).exists(): raise ValidationError('An active appointment already exists for this request.')
        run=draft.schedule_runs.first()
        if not run or request.data.get('run_id')!=run.pk: raise ValidationError('Refresh scheduling results first.')
        if run.result.get('duration_minutes')!=30: raise ValidationError('Refresh to use the current 30-minute consultation policy.')
        if run.result.get('alternative_offer') and request.data.get('accept_alternative') is not True: raise ValidationError('Confirm that the alternative time works for you.')
        fid=request.data.get('faculty_id'); start=request.data.get('start'); end=request.data.get('end'); mode=request.data.get('mode')
        if fid not in run.result['display_ids']: raise ValidationError('Select a displayed candidate.')
        old=next((c for c in run.result['candidates'] if c['faculty_id']==fid),None)
        def matches(s): return (s['start'],s['end'],s['mode'])==(start,end,mode)
        if not old or not any(matches(s) for s in old['slots']): raise ValidationError('Select a displayed slot.')
        f=get_object_or_404(FacultyProfile.objects.select_for_update(),faculty_id=fid,status='Active')
        current=checked(lambda:build(draft,run.result['preferences']))
        candidate=next((c for c in current['candidates'] if c['faculty_id']==fid and fid in current['display_ids']),None)
        if not candidate or not any(matches(s) for s in candidate['slots']): raise ValidationError('This option changed. Check availability again.')
        from datetime import datetime
        SlotSelection.objects.update_or_create(draft=draft,defaults={'run':run,'faculty':f,'start':datetime.fromisoformat(start),'end':datetime.fromisoformat(end),'mode':mode})
        return Response(payload(request,draft,run))

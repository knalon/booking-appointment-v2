from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Appointment, Notification
from .booking import submit, transition, expire, HELD
from .faculty_access import faculty_for
from apps.matching.views import Recommendation
from apps.nlp.views import profiles


def visible(user):
    qs=Appointment.objects.select_related('draft__session__learner','faculty')
    if user.is_staff: return qs
    f=faculty_for(user)
    if f: return qs.filter(faculty=f)
    return qs.filter(draft__session__owner=user,draft__session__learner__in=profiles(user))


def serialize(a,user):
    session=a.draft.session; learner=session.learner
    role='management' if user.is_staff else 'learner' if session.owner_id==user.pk else 'faculty'
    req=a.draft.final_result['request']
    from .teams import public_status
    return {'teams':public_status(a,user),'id':a.pk,'request_id':str(session.pk),'faculty_name':a.faculty.full_name,'faculty_id':a.faculty.faculty_id,'learner_name':learner.full_name,'learner_id':learner.learner_id,'module':req.get('module_code'),'difficulty':req.get('difficulty'),'language':req.get('preferred_language'),'urgency':req.get('urgency'),'start':a.start.isoformat(),'end':a.end.isoformat(),'mode':a.mode,'status':a.status,'expires_at':a.expires_at.isoformat() if a.expires_at else None,'role':role,'time_zone':a.faculty.time_zone if role=='faculty' else learner.time_zone,'events':list(a.events.order_by('pk').values('action','detail','created_at'))}


def expire_visible(user):
    ids=list(visible(user).filter(status__in=HELD,expires_at__lte=timezone.now()).values_list('pk',flat=True))
    for pk in ids:
        with transaction.atomic():
            a=Appointment.objects.select_for_update().get(pk=pk)
            expired=expire(a)
            draft_id=a.draft_id
        if expired:
            from apps.coordinator.services import sync_case
            sync_case(draft_id)


class Appointments(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        expire_visible(request.user)
        qs=visible(request.user)
        if request.query_params.get('request_id'): qs=qs.filter(draft__session_id=request.query_params['request_id'])
        return Response([serialize(a,request.user) for a in qs[:100]])
    def post(self,request):
        if request.user.is_staff or faculty_for(request.user): raise PermissionDenied('Learner access required.')
        try: draft=Recommendation().draft(request,request.data.get('request_id'))
        except (ValueError,TypeError): raise ValidationError('Invalid request ID.') from None
        a,created=submit(draft.pk,request.user,request.data.get('selection'))
        return Response(serialize(a,request.user),status=201 if created else 200)

class AppointmentAction(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request,pk):
        get_object_or_404(visible(request.user),pk=pk)
        a=transition(pk,request.user,request.data.get('action'),request.data)
        return Response(serialize(a,request.user))

def notification_scope(user):
    from apps.coordinator.access import scoped_cases
    from apps.coordinator.models import ReviewCase
    owned=ReviewCase.objects.filter(draft__session__owner=user,draft__session__learner__user=user,draft__session__learner__status='Active')
    case_ids=scoped_cases(user).values('pk')
    return Notification.objects.filter(recipient=user).filter(Q(appointment__isnull=False)|Q(review_case_id__in=case_ids)|Q(review_case_id__in=owned.values('pk')))


class Notifications(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        expire_visible(request.user)
        qs=notification_scope(request.user)
        return Response({'unread':qs.filter(read_at__isnull=True).count(),'items':list(qs.values('id','appointment_id','review_case_id','message','created_at','read_at')[:50])})
    def post(self,request):
        qs=notification_scope(request.user).filter(read_at__isnull=True)
        if request.data.get('all') is not True:
            pk=request.data.get('id')
            if type(pk) is not int: raise ValidationError('Provide a notification ID.')
            get_object_or_404(notification_scope(request.user),pk=pk)
            qs=qs.filter(pk=pk)
        qs.update(read_at=timezone.now())
        return self.get(request)

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from apps.nlp.models import ConsultationDraft
from apps.nlp.views import profiles
from .models import MatchingPolicy
from .policy import validate_policy
from .services import active_policy, create_run

class Policy(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        if not request.user.is_staff: raise PermissionDenied()
        row,config=active_policy(); return Response({'version':row.pk if row else 'original-v1','configuration':config,'can_edit':request.user.is_superuser})
    def post(self,request):
        if not request.user.is_staff or not request.user.is_superuser: raise PermissionDenied('Only the process-owner administrator may change policy.')
        try: config=validate_policy(request.data)
        except ValueError as e: raise ValidationError(str(e)) from None
        row=MatchingPolicy.objects.create(configuration=config,created_by=request.user)
        return Response({'version':row.pk,'configuration':config,'can_edit':True},status=201)

class Recommendation(APIView):
    permission_classes=[IsAuthenticated]
    def draft(self,request,pk,lock=False):
        qs=ConsultationDraft.objects.filter(session_id=pk,session__status='confirmed',final_result__isnull=False,session__owner__is_staff=False,session__owner__is_superuser=False)
        if not request.user.is_staff: qs=qs.filter(session__owner=request.user,session__learner__in=profiles(request.user))
        return get_object_or_404(qs.select_for_update() if lock else qs)
    def payload(self,request,run):
        if not run: return {'result':None}
        result=run.result
        if request.user.is_staff: return {'result':result}
        ids=result.get('display_ids',[]); candidates={c['faculty_id']:c for c in result['candidates']}
        safe=['faculty_id','name','department','expertise_level','match_type','currently_teaching','preferred_faculty_match','languages','modes','teaching_years','reasons','availability_status','academic_band']
        return {'result':{**{k:result[k] for k in ('request_id','recommendation_id','status','review_reason','availability_checked','booking_status','preferred_faculty_status')},'candidates':[{k:candidates[i][k] for k in safe} for i in ids]}}
    def get(self,request,pk):
        draft=self.draft(request,pk);return Response(self.payload(request,draft.recommendations.first()))
    @transaction.atomic
    def post(self,request,pk):
        draft=self.draft(request,pk,True); run=draft.recommendations.first()
        rerun=request.data.get('rerun') is True
        if rerun and not request.user.is_staff: raise PermissionDenied('Only management can rerun an existing recommendation.')
        if not run or rerun: run=create_run(draft)
        return Response(self.payload(request,run))

class History(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request,pk):
        if not request.user.is_staff: raise PermissionDenied()
        draft=Recommendation().draft(request,pk)
        return Response(list(draft.recommendations.values('id','created_at','result')[:50]))

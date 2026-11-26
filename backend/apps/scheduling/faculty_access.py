"""Faculty-only identity, independent of management and learner roles."""
import json
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.directory.models import FacultyProfile, LearnerProfile


def faculty_for(user):
    if not user.is_authenticated or not user.is_active or user.is_staff or user.is_superuser:
        return None
    if LearnerProfile.objects.filter(user=user).exists():
        return None
    return FacultyProfile.objects.filter(user=user,status='Active').first()


@csrf_protect
@require_POST
def sign_in(request):
    try:
        data=json.loads(request.body)
        user=authenticate(request,username=data['username'],password=data['password'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'detail':'Invalid login request.'},status=400)
    if user is None or faculty_for(user) is None:
        return JsonResponse({'detail':'Invalid credentials or faculty access not granted.'},status=403)
    login(request,user)
    return JsonResponse({'csrfToken':get_token(request)})


class FacultySession(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        f=faculty_for(request.user)
        if f is None: raise PermissionDenied('Faculty access required.')
        return Response({'username':request.user.get_username(),'faculty_id':f.faculty_id,'full_name':f.full_name,'department':f.department,'time_zone':f.time_zone,'working_days':f.working_days,'working_hours_start':f.working_hours_start,'working_hours_end':f.working_hours_end,'consultation_modes':f.consultation_modes,'csrfToken':get_token(request)})

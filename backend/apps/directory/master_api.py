"""React management endpoints; use the same validation as CSV import."""
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.db import transaction, IntegrityError
from rest_framework.response import Response
from .management_api import StaffView, FacultyEditSerializer
from .models import FacultyProfile
from apps.data_imports.services import HEADERS, MODELS, export_row, lookup, validate_records, save_row
from apps.data_imports.models import ImportBatch
import json

@ensure_csrf_cookie
@require_http_methods(['GET'])
def csrf(request):
    return JsonResponse({'csrfToken':get_token(request)})

@csrf_protect
@require_http_methods(['POST'])
def sign_in(request):
    try: data=json.loads(request.body); user=authenticate(request,username=data['username'],password=data['password'])
    except (ValueError, KeyError, TypeError): return JsonResponse({'detail':'Invalid login request.'},status=400)
    if not user or not user.is_active or not user.is_staff:
        return JsonResponse({'detail':'Invalid credentials or management access not granted.'},status=403)
    login(request,user)
    return JsonResponse({'username':user.get_username(),'csrfToken':get_token(request)})

@csrf_protect
@require_http_methods(['POST'])
def sign_out(request):
    logout(request)
    return JsonResponse({'csrfToken':get_token(request)})

class MasterRows(StaffView):
    def get(self,request,dataset):
        if dataset not in MODELS: return Response({'detail':'Unknown dataset.'},status=404)
        model,key,_=MODELS[dataset]
        order=['qualification__code','sequence','module__code'] if dataset=='curriculum' else [key]
        return Response([export_row(dataset,o) for o in model.objects.order_by(*order)])

    def post(self,request,dataset):
        if dataset not in MODELS: return Response({'detail':'Unknown dataset.'},status=404)
        if dataset=='faculty': return Response({'detail':'Use faculty profile editor.'},status=400)
        row=request.data.get('row'); original=request.data.get('original')
        if not isinstance(row,dict) or set(row)!=set(HEADERS[dataset]) or not all(isinstance(v,str) for v in row.values()):
            return Response({'detail':'Invalid record fields.'},status=400)
        row={k:v.strip() for k,v in row.items()}
        try:
            with transaction.atomic():
                for model,key,_ in MODELS.values(): list(model.objects.select_for_update().order_by('pk').values_list('pk',flat=True))
                obj=lookup(dataset,row)
                if original is None and obj: return Response({'detail':'Identifier already exists.'},status=409)
                if original is not None and (not obj or export_row(dataset,obj)!=original): return Response({'detail':'Record changed or identifier modified. Reload and try again.'},status=409)
                errors=validate_records(dataset,[row])
                if errors: return Response({'detail':'; '.join(f"{e['field']}: {e['message']}" for e in errors)},status=400)
                save_row(dataset,row)
                return Response(export_row(dataset,lookup(dataset,row)))
        except IntegrityError: return Response({'detail':'Database conflict. No changes saved.'},status=409)

class FacultyCreate(StaffView):
    @transaction.atomic
    def post(self,request):
        ident=str(request.data.get('faculty_id','')).strip()
        if not ident or len(ident)>30 or FacultyProfile.objects.filter(faculty_id=ident).exists(): return Response({'detail':'Provide a unique faculty ID (maximum 30 characters).'},status=400)
        s=FacultyEditSerializer(data=request.data,context={'creating':True});s.is_valid(raise_exception=True)
        try:
            with transaction.atomic(): f=s.save(faculty_id=ident)
        except IntegrityError: return Response({'detail':'Faculty identifier already exists.'},status=409)
        return Response({'faculty_id':f.faculty_id},status=201)

class History(StaffView):
    def get(self,request):
        return Response(list(ImportBatch.objects.order_by('-created_at').values('id','dataset','source_filename','state','total_rows','created_count','updated_count','unchanged_count','created_at','created_by__username')[:200]))

class TemplateHeaders(StaffView):
    def get(self,request,dataset):
        if dataset not in HEADERS:return Response({'detail':'Unknown dataset.'},status=404)
        return Response({'headers':HEADERS[dataset]})

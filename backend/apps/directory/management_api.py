from django.db import transaction, IntegrityError
from django.middleware.csrf import get_token
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.authentication import SessionAuthentication
from django.shortcuts import get_object_or_404
from .models import FacultyProfile, FacultyExpertise, AcademicModule, AcademicTopic, Qualification, QualificationModule
from .expertise_rules import expertise_errors

class StaffView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]

class SessionView(StaffView):
    def get(self, request):
        return Response({'username': request.user.get_username(), 'csrfToken': get_token(request)})

class ExpertiseSerializer(serializers.ModelSerializer):
    module = serializers.SlugRelatedField(slug_field='code', queryset=AcademicModule.objects.all())
    catalogue_topics = serializers.SlugRelatedField(slug_field='code', many=True, queryset=AcademicTopic.objects.all())
    qualifications = serializers.SlugRelatedField(slug_field='code', many=True, queryset=Qualification.objects.all())
    class Meta:
        model = FacultyExpertise
        fields = ['id','module','catalogue_topics','qualifications','expertise_level','verified_by','last_reviewed','eligible_for_consultation']
    def validate(self, attrs):
        old = self.instance
        def value(k, default=None):
            if k in attrs: return attrs[k]
            if old:
                v = getattr(old,k)
                return list(v.all()) if k in ('catalogue_topics','qualifications') else v
            return default
        faculty = self.context['faculty']
        module = value('module')
        if old and old.module_id != module.pk:
            raise serializers.ValidationError({'module':'Existing expertise module cannot be changed. Add a new record instead.'})
        if FacultyExpertise.objects.filter(faculty=faculty,module=module).exclude(pk=old.pk if old else None).exists():
            raise serializers.ValidationError({'module':'Expertise already exists for this module.'})
        errors = expertise_errors(faculty,module,value('catalogue_topics',[]),value('qualifications',[]),value('eligible_for_consultation',False),value('verified_by',''),value('last_reviewed'))
        if errors: raise serializers.ValidationError(errors)
        return attrs

class FacultyEditSerializer(serializers.ModelSerializer):
    qualifications = serializers.SlugRelatedField(slug_field='code', many=True, queryset=Qualification.objects.all())
    modules_taught = serializers.SlugRelatedField(slug_field='code', many=True, queryset=AcademicModule.objects.all())
    teaching_experience_years = serializers.IntegerField(min_value=0,max_value=60)
    languages = serializers.ListField(child=serializers.CharField(max_length=80), allow_empty=False)
    consultation_modes = serializers.ListField(child=serializers.ChoiceField(choices=['Online','Face-to-face']), allow_empty=False)
    working_days = serializers.ListField(child=serializers.ChoiceField(choices=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']), allow_empty=False)
    class Meta:
        model = FacultyProfile
        fields = ['faculty_id','full_name','email','department','status','languages','modules_taught','qualifications','teaching_experience_years','consultation_modes','time_zone','working_days','working_hours_start','working_hours_end']
        read_only_fields = ['faculty_id']
    def validate_languages(self, values):
        if not any(v.strip().casefold() == 'english' for v in values):
            raise serializers.ValidationError('English is required.')
        return list(dict.fromkeys('English' if v.casefold()=='english' else v for v in values))
    def validate_time_zone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError): raise serializers.ValidationError('Use a valid IANA time zone.')
        return value
    def validate(self, attrs):
        old = self.instance
        start = attrs.get('working_hours_start', getattr(old,'working_hours_start',None))
        end = attrs.get('working_hours_end', getattr(old,'working_hours_end',None))
        if (start is None) != (end is None) or (start and end and start >= end):
            raise serializers.ValidationError({'working_hours_end':'Provide both times with end after start.'})
        selected_qualifications = attrs.get('qualifications', list(old.qualifications.all()) if old else [])
        selected_modules = attrs.get('modules_taught', list(old.modules_taught.all()) if old else [])
        allowed_modules = set(QualificationModule.objects.filter(
            qualification__in=selected_qualifications, qualification__is_active=True,
            module__is_active=True, is_active=True
        ).values_list('module_id', flat=True))
        invalid = sorted(m.code for m in selected_modules if m.pk not in allowed_modules)
        if invalid and attrs.get("status",getattr(old,"status","Active"))=="Active":
            raise serializers.ValidationError({'modules_taught': 'Modules must belong to an active curriculum of a selected active qualification: ' + ', '.join(invalid)})
        return attrs

class FacultyDetailView(StaffView):
    def get(self, request, faculty_id):
        f = get_object_or_404(FacultyProfile,faculty_id=faculty_id)
        return Response(self.payload(f))
    def payload(self, f):
        return {**FacultyEditSerializer(f).data,'expertise':ExpertiseSerializer(f.expertise_mappings.all().order_by('module__code'),many=True).data,'admin_id':f.pk}
    @transaction.atomic
    def patch(self, request, faculty_id):
        f = get_object_or_404(FacultyProfile.objects.select_for_update(),faculty_id=faculty_id)
        serializer = FacultyEditSerializer(f,data=request.data,partial=True)
        serializer.is_valid(raise_exception=True)
        selected=serializer.validated_data.get('qualifications',list(f.qualifications.all()))
        allowed={q.pk for q in selected}
        changes=[]
        for e in f.expertise_mappings.select_for_update().all():
            before=list(e.qualifications.all()); after=[q for q in before if q.pk in allowed]
            if len(after)!=len(before):
                changes.append({'id':e.pk,'module':e.module.code,'removed':sorted(q.code for q in before if q.pk not in allowed),'revoke':bool(e.eligible_for_consultation and not after)})
        import hashlib,json
        token=hashlib.sha256(json.dumps([self.payload(f),request.data.get('qualifications'),request.data.get('modules_taught'),changes],sort_keys=True,default=str).encode()).hexdigest()
        removed_modules=sorted(set(f.modules_taught.values_list('code',flat=True))-{m.code for m in serializer.validated_data.get('modules_taught',list(f.modules_taught.all()))})
        if (changes or removed_modules) and request.data.get('impact_token')!=token:
            return Response({'detail':'Confirm affected expertise relationships.','impact':changes,'removed_modules':removed_modules,'impact_token':token},status=409)
        serializer.save()
        for change in changes:
            e=f.expertise_mappings.get(pk=change['id'])
            e.qualifications.remove(*list(e.qualifications.exclude(pk__in=allowed)))
            if change['revoke']:
                e.eligible_for_consultation=False;e.save(update_fields=['eligible_for_consultation'])
        return Response(self.payload(f))

class ExpertiseWriteView(StaffView):
    @transaction.atomic
    def post(self, request, faculty_id, expertise_id=None):
        if expertise_id is not None: return Response({"detail":"Use PATCH for an existing record."},status=405)
        f=get_object_or_404(FacultyProfile.objects.select_for_update(),faculty_id=faculty_id)
        s=ExpertiseSerializer(data=request.data,context={'faculty':f}); s.is_valid(raise_exception=True)
        s.save(faculty=f)
        return Response(s.data,status=201)
    @transaction.atomic
    def patch(self, request, faculty_id, expertise_id=None):
        if expertise_id is None: return Response({'detail':'Expertise ID required.'},status=400)
        f=get_object_or_404(FacultyProfile.objects.select_for_update(),faculty_id=faculty_id)
        e=get_object_or_404(FacultyExpertise.objects.select_for_update(),faculty=f,pk=expertise_id)
        s=ExpertiseSerializer(e,data=request.data,partial=True,context={'faculty':f}); s.is_valid(raise_exception=True); s.save()
        return Response(s.data)

class CurriculumReadView(StaffView):
    def get(self,request):
        return Response(list(QualificationModule.objects.order_by('qualification__code','sequence').values('qualification__code','module__code','sequence','is_active')))

class IntegrityView(StaffView):
    def get(self,request):
        issues=[]
        for e in FacultyExpertise.objects.select_related('faculty','module').prefetch_related('catalogue_topics','qualifications'):
            errors=expertise_errors(e.faculty,e.module,list(e.catalogue_topics.all()),list(e.qualifications.all()),e.eligible_for_consultation,e.verified_by,e.last_reviewed)
            if errors: issues.append({'faculty_id':e.faculty.faculty_id,'module':e.module.code,'id':e.pk,'errors':errors})
        return Response({'issues':issues})

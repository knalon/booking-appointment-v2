from django.contrib import admin
from django import forms
from .models import AcademicTopic, QualificationModule
from .models import Qualification, AcademicModule, FacultyProfile, FacultyExpertise, LearnerProfile

@admin.action(description='Archive selected records')
def archive(modeladmin,request,queryset): queryset.update(is_active=False)
@admin.action(description='Restore selected records')
def restore(modeladmin,request,queryset): queryset.update(is_active=True)

class CatalogueAdmin(admin.ModelAdmin):
    actions=[archive,restore]
    list_filter=('is_active',)
    search_fields=('code','name')
    def get_readonly_fields(self,request,obj=None): return ('code',) if obj else ()
    def has_delete_permission(self,request,obj=None): return False

class CurriculumForm(forms.ModelForm):
    class Meta:
        model=QualificationModule
        fields='__all__'
    def clean(self):
        data=super().clean()
        p,m,seq=data.get('qualification'),data.get('module'),data.get('sequence')
        if seq is not None and seq < 1: self.add_error('sequence','Sequence must be positive.')
        if p and m and data.get('is_active') and QualificationModule.objects.filter(qualification=p,sequence=seq,is_active=True).exclude(pk=self.instance.pk).exists(): self.add_error('sequence','This sequence is already in use. Use CSV for bulk reordering.')
        if p and m and not data.get('is_active') and LearnerProfile.objects.filter(qualification=p,current_modules=m,status='Active').exists(): self.add_error('is_active','Reassign active learners first.')
        return data

@admin.register(QualificationModule)
class CurriculumAdmin(admin.ModelAdmin):
    form=CurriculumForm
    list_display=('qualification','sequence','module','is_active')
    list_filter=('qualification','is_active')
    search_fields=('qualification__name','qualification__code','module__code','module__name')
    def has_delete_permission(self,request,obj=None): return False
    def get_readonly_fields(self,request,obj=None): return ('qualification','module') if obj else ()

@admin.register(Qualification)
class QualificationAdmin(CatalogueAdmin):
    list_display=('code','name','is_active','curriculum_link')
    def get_readonly_fields(self,request,obj=None): return ('code','curriculum_link') if obj else ('curriculum_link',)
    @admin.display(description='Qualification curriculum')
    def curriculum_link(self,obj):
        if not obj.pk: return 'Save qualification first.'
        from django.urls import reverse
        from django.utils.html import format_html, format_html_join
        link=reverse('admin:directory_qualificationmodule_changelist')
        entries=format_html_join('', '<li>{}: {} — {} ({})</li>', ((c.sequence,c.module.code,c.module.name,'Active' if c.is_active else 'Archived') for c in obj.curriculum.select_related('module').order_by('sequence')))
        return format_html('<ol>{}</ol><a href="{}?qualification__id__exact={}">Manage curriculum</a>',entries,link,obj.pk)

@admin.register(AcademicModule)
class ModuleAdmin(CatalogueAdmin):
    list_display=('code','name','department','is_active','topics_link')
    @admin.display(description='Topic catalogue')
    def topics_link(self,obj):
        from django.urls import reverse
        from django.utils.html import format_html
        return format_html('<a href="{}?module__id__exact={}">Manage topics ({})</a>',reverse('admin:directory_academictopic_changelist'),obj.pk,obj.topic_catalogue.count())
    exclude=('qualifications',)

@admin.register(FacultyProfile)
class FacultyAdmin(admin.ModelAdmin):
    list_display=('faculty_id','full_name','department','status')
    search_fields=('faculty_id','full_name','email')
    list_filter=('status','department')
    filter_horizontal=('qualifications','modules_taught')
    readonly_fields=('additional_modules_taught',)

class LearnerForm(forms.ModelForm):
    class Meta:
        model=LearnerProfile
        fields='__all__'
    def clean(self):
        data=super().clean()
        qualification=data.get('qualification'); selected=data.get('current_modules'); primary=data.get('current_module')
        if qualification and selected is not None:
            valid=QualificationModule.objects.filter(qualification=qualification,is_active=True).values_list('module_id',flat=True)
            if selected.exclude(pk__in=valid).exists(): self.add_error('current_modules','Select modules in the active qualification curriculum.')
            if not primary or not selected.filter(pk=primary.pk).exists(): self.add_error('current_module','Primary module must be selected among current modules.')
        if not qualification: self.add_error('qualification','Select a qualification.')
        langs=data.get('preferred_languages') or []
        if not isinstance(langs,list) or not any(isinstance(x,str) and x.casefold()=='english' for x in langs): self.add_error('preferred_languages','English is mandatory.')
        return data

@admin.register(LearnerProfile)
class LearnerAdmin(admin.ModelAdmin):
    form=LearnerForm
    filter_horizontal=('current_modules',)
    list_display=('learner_id','full_name','qualification','current_module','status')
    search_fields=('learner_id','full_name','email')
    list_filter=('status','qualification')

@admin.register(AcademicTopic)
class TopicAdmin(CatalogueAdmin):
    list_display=('code','name','module','is_active','coverage')
    list_filter=('is_active','module')
    search_fields=('code','name','module__code','module__name')
    def get_readonly_fields(self,request,obj=None): return ('code','module') if obj else ()
    @admin.display(description='Approved active faculty')
    def coverage(self,obj):
        if not obj.is_active or not obj.module.is_active: return 0
        return obj.faculty_expertise.filter(eligible_for_consultation=True,faculty__status='Active').values('faculty_id').distinct().count()

from .expertise_rules import expertise_errors

class ExpertiseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and "module" in self.fields:
            self.fields["module"].disabled = True
        if self.instance.pk and "catalogue_topics" in self.fields:
            # Include previously selected mismatches so administrators can remove them.
            from django.db.models import Q
            self.fields["catalogue_topics"].queryset = AcademicTopic.objects.filter(Q(module_id=self.instance.module_id) | Q(pk__in=self.instance.catalogue_topics.values_list("pk", flat=True))).order_by("name")
    class Meta:
        model=FacultyExpertise
        exclude=('topics',)
    def clean(self):
        data=super().clean()
        module=data.get('module') or getattr(self.instance,'module',None)
        selected=data.get('catalogue_topics')
        qualifications=data.get('qualifications')
        faculty=data.get('faculty') or getattr(self.instance,'faculty',None)
        if module and selected is not None and qualifications is not None:
            for field,message in expertise_errors(faculty,module,list(selected),list(qualifications),data.get('eligible_for_consultation'),data.get('verified_by'),data.get('last_reviewed')).items():
                self.add_error(field,message)
        return data

class ExpertiseInline(admin.StackedInline):
    model=FacultyExpertise
    form=ExpertiseForm
    extra=0
    can_delete=False
    filter_horizontal=('catalogue_topics','qualifications')
    def formfield_for_manytomany(self,db_field,request,**kwargs):
        if db_field.name=='catalogue_topics': kwargs['queryset']=AcademicTopic.objects.select_related('module').order_by('module__code','name')
        return super().formfield_for_manytomany(db_field,request,**kwargs)

@admin.register(FacultyExpertise)
class ExpertiseAdmin(admin.ModelAdmin):
    form=ExpertiseForm
    list_display=('faculty','module','expertise_level','eligible_for_consultation')
    list_filter=('module','expertise_level','eligible_for_consultation')
    search_fields=('faculty__full_name','faculty__faculty_id','module__name','catalogue_topics__name')
    filter_horizontal=('catalogue_topics','qualifications')
    def get_readonly_fields(self,request,obj=None): return ('faculty','module') if obj else ()
    def has_delete_permission(self,request,obj=None): return False
    def formfield_for_manytomany(self,db_field,request,**kwargs):
        if db_field.name=='catalogue_topics':
            qs=AcademicTopic.objects.select_related('module').order_by('module__code','name')
            object_id=request.resolver_match.kwargs.get('object_id') if request.resolver_match else None
            if object_id:
                exp=FacultyExpertise.objects.filter(pk=object_id).first()
                if exp: qs=qs.filter(module_id=exp.module_id)
            kwargs['queryset']=qs
        return super().formfield_for_manytomany(db_field,request,**kwargs)

FacultyAdmin.inlines=[ExpertiseInline]


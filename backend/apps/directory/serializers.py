from rest_framework import serializers
from .models import FacultyProfile, LearnerProfile

class FacultyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultyProfile
        fields = ["faculty_id", "full_name", "email", "department", "teaching_experience_years",
                  "consultation_modes", "languages", "time_zone", "working_days",
                  "working_hours_start", "working_hours_end", "status"]

class LearnerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearnerProfile
        fields = ["learner_id", "full_name", "email", "time_zone",
                  "preferred_consultation_modes", "preferred_languages", "status"]

from .models import Qualification, AcademicModule

class CatalogueSerializer(serializers.ModelSerializer):
    def validate_code(self,value):
        import re
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,29}',value):
            raise serializers.ValidationError('Use uppercase letters, digits, hyphens or underscores.')
        if self.instance and value != self.instance.code:
            raise serializers.ValidationError('Existing codes are immutable.')
        return value

class QualificationSerializer(CatalogueSerializer):
    class Meta:
        model=Qualification
        fields=['code','name','is_active']

class ModuleSerializer(CatalogueSerializer):
    qualifications=serializers.SlugRelatedField(many=True,slug_field='code',read_only=True)
    class Meta:
        model=AcademicModule
        fields=['code','name','department','qualifications','is_active']


from .models import AcademicTopic
class TopicSerializer(CatalogueSerializer):
    module=serializers.SlugRelatedField(slug_field='code',queryset=AcademicModule.objects.all())
    def validate(self,attrs):
        module=attrs.get('module',getattr(self.instance,'module',None))
        name=attrs.get('name',getattr(self.instance,'name',''))
        if self.instance and module != self.instance.module:
            raise serializers.ValidationError('Topic module is immutable.')
        qs=AcademicTopic.objects.filter(module=module,name__iexact=name)
        if self.instance: qs=qs.exclude(pk=self.instance.pk)
        if qs.exists(): raise serializers.ValidationError('Topic already exists in module.')
        return attrs
    class Meta:
        model=AcademicTopic
        fields=['code','module','name','is_active']

from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from .models import FacultyProfile, LearnerProfile
from .serializers import FacultyProfileSerializer, LearnerProfileSerializer

class FacultyListView(generics.ListAPIView):
    queryset = FacultyProfile.objects.all().order_by("faculty_id")
    serializer_class = FacultyProfileSerializer
    permission_classes = [IsAdminUser]

class LearnerListView(generics.ListAPIView):
    queryset = LearnerProfile.objects.all().order_by("learner_id")
    serializer_class = LearnerProfileSerializer
    permission_classes = [IsAdminUser]

from .models import Qualification, AcademicModule
from .serializers import QualificationSerializer, ModuleSerializer

class QualificationCatalogueView(generics.ListCreateAPIView):
    queryset=Qualification.objects.order_by('code')
    serializer_class=QualificationSerializer
    permission_classes=[IsAdminUser]

class ModuleCatalogueView(generics.ListCreateAPIView):
    queryset=AcademicModule.objects.order_by('code')
    serializer_class=ModuleSerializer
    permission_classes=[IsAdminUser]

class CatalogueDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes=[IsAdminUser]
    lookup_field='code'
    def perform_destroy(self,instance):
        instance.is_active=False
        instance.save(update_fields=['is_active'])

class QualificationDetail(CatalogueDetail):
    queryset=Qualification.objects.all()
    serializer_class=QualificationSerializer

class ModuleDetail(CatalogueDetail):
    queryset=AcademicModule.objects.all()
    serializer_class=ModuleSerializer


from .models import AcademicTopic
from .serializers import TopicSerializer
class TopicCatalogueView(generics.ListCreateAPIView):
    serializer_class=TopicSerializer
    permission_classes=[IsAdminUser]
    def get_queryset(self):
        qs=AcademicTopic.objects.select_related('module').order_by('module__code','name')
        module=self.request.query_params.get('module')
        return qs.filter(module__code=module) if module else qs
class TopicDetail(CatalogueDetail):
    queryset=AcademicTopic.objects.all()
    serializer_class=TopicSerializer

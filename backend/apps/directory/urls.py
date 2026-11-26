from django.urls import path
from .views import FacultyListView, LearnerListView, QualificationCatalogueView, QualificationDetail, ModuleCatalogueView, ModuleDetail

from .views import TopicCatalogueView, TopicDetail

from .management_api import SessionView, FacultyDetailView, ExpertiseWriteView, CurriculumReadView, IntegrityView

urlpatterns = [
    path("session/", SessionView.as_view()),
    path("integrity/", IntegrityView.as_view()),
    path("curriculum/", CurriculumReadView.as_view()),
    path("faculty/<str:faculty_id>/", FacultyDetailView.as_view()),
    path("faculty/<str:faculty_id>/expertise/", ExpertiseWriteView.as_view()),
    path("faculty/<str:faculty_id>/expertise/<int:expertise_id>/", ExpertiseWriteView.as_view()),
    path("programmes/", QualificationCatalogueView.as_view()),  # legacy URL alias
    path("programmes/<str:code>/", QualificationDetail.as_view()),
    path("topics/", TopicCatalogueView.as_view()),
    path("topics/<str:code>/", TopicDetail.as_view()),
    path("qualifications/", QualificationCatalogueView.as_view()),
    path("qualifications/<str:code>/", QualificationDetail.as_view()),
    path("modules/", ModuleCatalogueView.as_view()),
    path("modules/<str:code>/", ModuleDetail.as_view()),
    path("faculty/", FacultyListView.as_view(), name="faculty-list"),
    path("learners/", LearnerListView.as_view(), name="learner-list"),
]

from . import master_api
urlpatterns = [
 path("auth/csrf/",master_api.csrf),path("auth/login/",master_api.sign_in),path("auth/logout/",master_api.sign_out),
 path("master/<str:dataset>/",master_api.MasterRows.as_view()),path("create-faculty/",master_api.FacultyCreate.as_view()),path("import-history/",master_api.History.as_view()),path("template/<str:dataset>/",master_api.TemplateHeaders.as_view()),
] + urlpatterns

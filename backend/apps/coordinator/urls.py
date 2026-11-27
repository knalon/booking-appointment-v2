from django.urls import path
from . import views
urlpatterns=[path('login/',views.sign_in),path('session/',views.Session.as_view()),path('accounts/',views.Accounts.as_view()),path('cases/',views.Cases.as_view()),path('cases/<int:pk>/',views.CaseDetail.as_view()),path('learner-cases/',views.LearnerCases.as_view()),path('appointments/',views.Appointments.as_view())]

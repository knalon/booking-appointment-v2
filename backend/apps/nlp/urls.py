from django.urls import path
from .views import Status, Sessions, SessionDetail, Turn, learner_login, ConfirmedResults
urlpatterns=[path("confirmed-results/",ConfirmedResults.as_view()),path("login/",learner_login),path('status/',Status.as_view()),path('sessions/',Sessions.as_view()),path('sessions/<uuid:pk>/',SessionDetail.as_view()),path('sessions/<uuid:pk>/turn/',Turn.as_view())]

from django.urls import path
from .views import Policy, Recommendation, History
urlpatterns=[path('policy/',Policy.as_view()),path('requests/<uuid:pk>/',Recommendation.as_view()),path('requests/<uuid:pk>/history/',History.as_view())]

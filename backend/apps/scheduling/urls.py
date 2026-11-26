from django.urls import path
from .views import Availability,Schedule
from .faculty_access import FacultySession,sign_in
urlpatterns=[path("faculty/login/",sign_in),path("faculty/session/",FacultySession.as_view()),path('availability/',Availability.as_view()),path('requests/<uuid:pk>/',Schedule.as_view())]

from .booking_views import Appointments, AppointmentAction, Notifications
urlpatterns += [path("appointments/", Appointments.as_view()), path("appointments/<int:pk>/action/", AppointmentAction.as_view()), path("notifications/", Notifications.as_view())]

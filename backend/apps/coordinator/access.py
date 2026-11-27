from apps.directory.models import FacultyProfile, LearnerProfile
from .models import CoordinatorProfile, ReviewCase


def profile_for(user):
    if not user.is_authenticated or not user.is_active or user.is_staff or user.is_superuser:
        return None
    if FacultyProfile.objects.filter(user=user).exists() or LearnerProfile.objects.filter(user=user).exists():
        return None
    return CoordinatorProfile.objects.filter(user=user, active=True).first()


def scope_codes(profile):
    return profile.qualifications.filter(is_active=True).values_list('code', flat=True)


def scoped_cases(user):
    qs=ReviewCase.objects.select_related('draft__session__learner__qualification','qualification','assigned_to__user')
    if user.is_staff and user.is_active:
        return qs
    p=profile_for(user)
    if not p: return qs.none()
    from django.db.models import F
    return qs.filter(qualification__code__in=scope_codes(p),draft__session__learner__qualification_id=F('qualification_id'))


def scoped_appointments(user):
    from apps.scheduling.models import Appointment
    from django.db.models import F
    qs=Appointment.objects.select_related('draft__session__learner__qualification','faculty')
    if user.is_staff and user.is_active: return qs
    p=profile_for(user)
    if not p: return qs.none()
    # Match both current qualification and the immutable confirmed qualification.
    from django.db.models.fields.json import KeyTextTransform
    return qs.annotate(confirmed_qualification=KeyTextTransform('qualification_code','draft__final_result')).filter(draft__session__learner__qualification__code__in=scope_codes(p),confirmed_qualification=F('draft__session__learner__qualification__code'))

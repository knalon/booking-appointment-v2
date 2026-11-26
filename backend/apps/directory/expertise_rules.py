from .models import QualificationModule


def expertise_errors(faculty, module, topics, qualifications, eligible, verifier, reviewed):
    errors = {}
    if any(t.module_id != module.pk for t in topics):
        errors['catalogue_topics'] = 'Select topics belonging to this module only.'
    if faculty and faculty.pk:
        if set(q.pk for q in qualifications) - set(faculty.qualifications.values_list('pk', flat=True)):
            errors['qualifications'] = 'Qualifications must be assigned to this faculty member.'
    if eligible:
        if not qualifications:
            errors["qualifications"] = "Approved expertise requires at least one relevant qualification."
        if not verifier or not verifier.strip() or not reviewed:
            errors['eligible_for_consultation'] = 'Approval requires a verifier and review date.'
        if not module.is_active or any(not t.is_active for t in topics):
            errors['catalogue_topics'] = 'Approved expertise requires an active module and active topics.'
        valid = set(QualificationModule.objects.filter(module=module, is_active=True, qualification__is_active=True).values_list('qualification_id', flat=True))
        if any(q.pk not in valid for q in qualifications):
            errors['qualifications'] = 'Approved qualifications must contain this module in their active curriculum.'
    return errors

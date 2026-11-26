from .policy import LEVELS
from apps.nlp.routing import language_options

def key(value): return ''.join(c for c in str(value or '').casefold() if c.isalnum())

def assess(f, expertise, qualification, module, topic, request, policy):
    errors=[]
    if f.status!='Active': errors.append('Inactive faculty')
    if qualification.pk not in {q.pk for q in f.qualifications.all()}: errors.append('Qualification association missing')
    if not expertise: errors.append('No direct module expertise')
    else:
        if not expertise.eligible_for_consultation or not expertise.verified_by.strip() or not expertise.last_reviewed: errors.append('Expertise not approved or verification incomplete')
        if qualification.pk not in {q.pk for q in expertise.qualifications.all()}: errors.append('Expertise not approved for qualification')
        if expertise.expertise_level not in LEVELS: errors.append('Invalid expertise level')
    languages={key(x) for x in f.languages}
    try: acceptable={key(x) for x in language_options(request.get('preferred_language'))}
    except ValueError: acceptable=None
    if acceptable is None: errors.append('Requested language needs clarification')
    elif not languages or (acceptable and not acceptable.intersection(languages)): errors.append('Requested language unsupported')
    modes={key(x) for x in f.consultation_modes}&{'online','facetoface'}; mode=key(request.get('mode'))
    if not modes or (mode!='either' and mode not in modes): errors.append('Requested mode unsupported')
    exact=bool(topic and expertise and topic.pk in {t.pk for t in expertise.catalogue_topics.all() if t.is_active and t.module_id==module.pk})
    if topic and not exact and not policy['allow_module_fallback']: errors.append('Exact topic expertise required')
    return errors,exact

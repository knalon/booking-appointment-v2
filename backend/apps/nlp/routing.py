"""Consultation purpose, scope and supported-language normalization.

Rules are deliberately conservative. The model resolves ambiguous purposes;
no keyword rule grants faculty eligibility or invents academic catalogue codes.
"""
import re
import unicodedata

SCOPES = ('coursework', 'learner_project', 'institutional_system', 'administrative')
VALID_SCOPES = {'academic': {'coursework', 'learner_project'},
                'technical': {'coursework', 'learner_project', 'institutional_system'},
                'other': {'administrative'}}
LANGUAGES = ('English', 'Myanmar', 'Chinese')


def language_options(value):
    """Return acceptable languages, or raise for unrecognized requirements."""
    if not isinstance(value, str):
        raise ValueError('Specify an acceptable consultation language.')
    text = unicodedata.normalize('NFKC', value).casefold().strip()
    if text in {'any', 'either', 'flexible', 'no preference', 'any language', '不限', '随便', '都可以', 'အဆင်ပြေသလို'}:
        return []
    aliases = {'english': 'English', 'myanmar': 'Myanmar', 'burmese': 'Myanmar',
               'chinese': 'Chinese', 'mandarin': 'Chinese', '英语': 'English',
               '英文': 'English', '中文': 'Chinese', '汉语': 'Chinese', '缅甸语': 'Myanmar',
               'မြန်မာ': 'Myanmar', 'မြန်မာဘာသာ': 'Myanmar', 'အင်္ဂလိပ်': 'English', 'တရုတ်': 'Chinese'}
    # 'or', not 'and': the latter may mean a mandatory bilingual consultation.
    parts = re.split(r'\s*(?:\bor\b|/|,|;|、|或者|或|သို့မဟုတ်)\s*', text)
    if not parts or any(p.strip() not in aliases for p in parts):
        raise ValueError('Choose English, Myanmar, Chinese, or acceptable alternatives using “or”.')
    return list(dict.fromkeys(aliases[p.strip()] for p in parts))


def canonical_language(value):
    options = language_options(value)
    return 'flexible' if not options else ' or '.join(options)


def purpose_evidence(text):
    """High-precision English consistency checks, not a general classifier."""
    t = str(text or '').casefold()
    if re.search(r'\b(?:institutional|school|university|college|student)\s+(?:account|portal|network|email|wi-?fi)\b|\b(?:lms|learning platform)\b', t) and re.search(r'\b(?:access|login|log in|sign in|locked|password|connect|not working|reset)\b', t):
        return 'technical', 'institutional_system'
    if re.search(r'\b(?:qualification transfer|change (?:my |the )?qualification|enrolment issue|enrollment issue|tuition fee|assessment arrangements)\b', t):
        return 'other', 'administrative'
    project = bool(re.search(r'\b(?:my |our |learner |final |coursework |student |capstone )?project\b|\bassignment\b|\bcoursework\b', t))
    if project and re.search(r'\b(?:debug\w*|crash\w*|error\w*|fail\w*|troubleshoot\w*|install\w*|unable to connect|cannot connect|can.t connect|not working|connection problem)\b', t):
        return 'technical', 'learner_project' if 'project' in t else 'coursework'
    if re.search(r'\b(?:understand\w*|learn\w*|explain\w*|concept\w*|confused about|difficulty with|struggling with)\b', t) and not re.search(r'\b(?:install\w*|login|log in|access|crash\w*|error\w*|troubleshoot\w*|not working|password)\b', t):
        # Require academic evidence; do not convert every "understanding" request.
        if re.search(r'\b(?:python|programming|oop|object[ -]oriented|loops?|abstraction|encapsulation|polymorphism|inheritance|functions?|normalization|normalisation|algorithms?|sql|database|statistics|calculus|coursework|module|academic concept)\b', t):
            return 'academic', 'learner_project' if project and 'project' in t else 'coursework'
    return None


def stabilize_purpose(old, proposed, latest, clarification):
    """Prevent preference-only replies from reclassifying an established purpose."""
    result = dict(proposed)
    previous = (old.get('consultation_type'), old.get('consultation_scope'))
    incoming = (result.get('consultation_type'), result.get('consultation_scope'))
    established = previous[1] in VALID_SCOPES.get(previous[0], set())
    new_evidence = purpose_evidence(latest)
    # New explicit problem evidence can change routing; an answer to the scope
    # question may also legitimately resolve an ambiguous purpose.
    correction = bool(re.search(r'\b(?:actually|instead|i meant|not about|different issue|change my request)\b|其实|不是|改为', latest, re.I)) and bool(result.get('difficulty') and result.get('difficulty') != old.get('difficulty'))
    if established and clarification not in ('consultation_type', 'consultation_scope') and not new_evidence and not correction:
        result['consultation_type'], result['consultation_scope'] = previous
    elif new_evidence:
        result['consultation_type'], result['consultation_scope'] = new_evidence
    elif incoming[0] != previous[0] and incoming[1] not in VALID_SCOPES.get(incoming[0], set()):
        result['consultation_scope'] = None
    return result


def routing_for(data):
    kind, scope = data.get('consultation_type'), data.get('consultation_scope')
    if kind in ('academic', 'technical') and scope in ('coursework', 'learner_project'):
        return 'faculty_matching' if data.get('module_code') else 'coordinator_review'
    if kind == 'technical' and scope == 'institutional_system':
        return 'support_review'
    return 'coordinator_review'

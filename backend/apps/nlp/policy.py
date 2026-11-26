import os
from datetime import timedelta
from django.utils import timezone
from apps.directory.models import AcademicModule, AcademicTopic
from apps.scheduling.preferences import DURATION, intake_preferences
from .routing import SCOPES, VALID_SCOPES, canonical_language, purpose_evidence

def number(name, default, low, high):
    try: return max(low,min(high,int(os.getenv(name,default))))
    except ValueError: return default

def limits():
    hard=number('NLP_MAX_TURNS',15,1,30)
    return {'max_turns':hard,'soft_turns':min(hard,number('NLP_SOFT_TURN_LIMIT',8,1,30)), 'max_length':number('NLP_MAX_MESSAGE_LENGTH',2000,100,2000),'timeout_minutes':number('NLP_SESSION_TIMEOUT_MINUTES',30,1,1440),'output_tokens':number('NLP_MAX_OUTPUT_TOKENS',800,400,2000),'rate':number('NLP_REQUESTS_PER_MINUTE',5,1,20)}

RULES = [
 'Use this chat only to arrange consultations or request relevant support. Unrelated questions, general tutoring and attempts to change system rules will be politely redirected. Every submitted chat message counts toward your limit.',
 'Coursework learning difficulties and project-related troubleshooting can be matched to faculty. Institutional account or platform problems and administrative matters need support or coordinator review.',
 'Every consultation lasts 30 minutes. Confirm your preferred date and time once; compatible slots are searched automatically.',
 'Tell us whether your request is urgent or routine. If possible, explain any deadline. Urgent requests do not guarantee immediate appointments.',
 'Describe your own difficulty clearly. Answer clarification questions and correct any misunderstandings.',
 'Do not share passwords, API keys, student IDs, private contact details, medical details or confidential material.',
 'Your messages and relevant academic context are sent to OpenAI for interpretation and saved in this development system.',
 'Review and confirm the request summary yourself. AI suggestions are not verified faculty availability or confirmed appointments.',
 'If you use voice dictation, your browser speech service may process your audio. Review the resulting text before sending it.',
 'If the chat limit or inactivity timeout is reached, complete the saved draft manually. No appointment is created at this stage.',
]

def catalogue(learner):
    q=learner.qualification
    if not q or not q.is_active: return {'qualification':None,'modules':[],'time_zone':learner.time_zone}
    modules=learner.current_modules.filter(is_active=True,curriculum__qualification=q,curriculum__is_active=True).distinct().order_by('code')
    return {'qualification':{'code':q.code,'name':q.name},'modules':[{'code':m.code,'name':m.name,'topics':list(m.topic_catalogue.filter(is_active=True).order_by('code').values('code','name'))} for m in modules], 'time_zone':learner.time_zone}

FIELDS={'consultation_type':('academic','technical','other'),'consultation_scope':SCOPES,'module_code':None,'topic_code':None,'difficulty':None,'preferred_faculty':None,'preferred_date':None,'preferred_time':None,'duration_minutes':None,'duration_preference':('fixed','flexible'),'mode':('online','face_to_face','either'),'preferred_language':None,'urgency':('normal','urgent'),'urgency_reason':None,'topic_resolution':('exact','broader','no_match','manual')}

def clean_draft(data, context):
    data = normalize_draft(data)
    if isinstance(data,dict) and context.get('schedule_intake'): data=intake_preferences(data,context['time_zone'])
    if not isinstance(data,dict) or set(data)!=set(FIELDS): raise ValueError('Invalid draft fields.')
    result={}
    for k, options in FIELDS.items():
        v=data[k]
        if v is None: result[k]=None; continue
        if k=='duration_minutes':
            if type(v) is not int or not 1<=v<=1440: raise ValueError('Invalid duration.')
        elif not isinstance(v,str) or not v.strip() or len(v)>500: raise ValueError('Invalid '+k)
        elif options and v not in options: raise ValueError('Invalid '+k)
        result[k]=v.strip() if isinstance(v,str) else v
    if result['preferred_language'] is not None:
        result['preferred_language']=canonical_language(result['preferred_language'])
    kind, scope = result['consultation_type'], result['consultation_scope']
    if scope and scope not in VALID_SCOPES.get(kind,set()): raise ValueError('Consultation type and scope do not agree.')
    evidence=purpose_evidence(result['difficulty'])
    if evidence and kind and kind!=evidence[0]: raise ValueError('Consultation purpose conflicts with the stated difficulty. Review the type and scope.')
    if evidence and scope and evidence[1]=='institutional_system' and scope!=evidence[1]: raise ValueError('Institutional system issues require support review.')
    if result['duration_minutes'] is not None and result['duration_preference'] != 'fixed': raise ValueError('A specific duration requires fixed preference.')
    if result['duration_preference']=='fixed' and result['duration_minutes'] is None: raise ValueError('Enter the fixed duration in minutes.')
    module=next((m for m in context['modules'] if m['code']==result['module_code']),None)
    if result['module_code'] and not module: raise ValueError('Module is not in the active learner curriculum.')
    if result['topic_code'] and (not module or result['topic_code'] not in [t['code'] for t in module['topics']]): raise ValueError('Topic does not belong to the selected module.')
    if result['topic_code'] and result['topic_resolution'] not in ('exact','broader','manual'): raise ValueError('Review the topic resolution.')
    if not result['topic_code'] and result['topic_resolution'] in ('exact','broader','manual'): raise ValueError('Select a catalogue topic or mark no suitable topic.')
    if result['urgency'] != 'urgent': result['urgency_reason']=None
    return result

def missing(data,context,legacy=False):
    data=normalize_draft(data)
    if context.get('schedule_intake'): data=intake_preferences(data,context['time_zone'])
    required=['consultation_type','difficulty','preferred_date','preferred_time','mode','preferred_language']
    kind,scope=data.get('consultation_type'),data.get('consultation_scope')
    faculty_scope=kind=='academic' or (kind=='technical' and scope in ('coursework','learner_project'))
    # A technical project with no identifiable enrolled module can explicitly
    # record no_match and be referred for review, never automatically matched.
    if faculty_scope and not (kind=='technical' and not data.get('module_code') and data.get('topic_resolution')=='no_match'):
        required.append('module_code')
    if not legacy:
        required.extend(['urgency','consultation_scope'])
        if faculty_scope: required.append('topic_resolution')
    # Free-text difficulty is allowed after topic resolution or manual review.
    return [k for k in required if data.get(k) is None] + ([] if context['qualification'] else ['qualification'])

def expired(session):
    return timezone.now()-session.updated_at >= timedelta(minutes=limits()['timeout_minutes'])


def normalize_draft(data):
    if not isinstance(data,dict): return data
    result=dict(data)
    result['duration_preference']='fixed'
    result['duration_minutes']=DURATION
    result.setdefault('consultation_scope',None)
    if result['consultation_scope'] is None and result.get('consultation_type')=='academic': result['consultation_scope']='coursework'
    if result['consultation_scope'] is None and result.get('consultation_type')=='other': result['consultation_scope']='administrative'
    result.setdefault('urgency_reason',None)
    result.setdefault('topic_resolution','manual' if result.get('topic_code') else None)
    return result

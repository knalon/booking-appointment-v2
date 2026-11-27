from django.utils import timezone
from apps.directory.models import FacultyProfile, FacultyExpertise, AcademicTopic
from apps.nlp.policy import catalogue, clean_draft, missing
from apps.nlp.routing import routing_for
from .models import MatchingPolicy, RecommendationRun
from .policy import DEFAULT, LEVELS, academic_score
from .eligibility import assess,key


def active_policy():
    row=MatchingPolicy.objects.order_by('-pk').first()
    return row, row.configuration if row else DEFAULT


def calculate(draft, policy, version):
    s=draft.session; learner=s.learner; final=draft.final_result or {}; request=final.get('request',{})
    if not isinstance(request,dict): request={}
    result={'schema_version':'1.0','algorithm_version':'1.1.3','request_id':str(s.pk),'learner_id':learner.learner_id,'qualification_code':final.get('qualification_code'),'module_code':request.get('module_code'),'topic_code':request.get('topic_code'),'policy_version':version,'policy':policy,'status':'needs_review','review_reason':None,'candidates':[],'excluded':[],'eligible_candidate_count':0,'availability_checked':False,'booking_status':'not_booked','selected_faculty_id':None,'preferred_faculty_status':'not_requested'}
    def review(reason):
        result['review_reason']=reason; return result
    context=catalogue(learner)
    if learner.status!='Active' or learner.user_id!=s.owner_id or not context['qualification'] or final.get('qualification_code')!=context['qualification']['code'] or final.get('learner_id')!=learner.learner_id or final.get('request_id')!=str(s.pk): return review('Learner or qualification has changed; coordinator review required.')
    try:
        request=clean_draft(request,context)
        if missing(request,context,legacy=final.get('schema_version') not in ('1.1','1.2','1.3')): raise ValueError('Incomplete request')
    except (ValueError,TypeError,KeyError): return review('Confirmed academic details no longer valid; coordinator review required.')
    # Historical non-academic snapshots did not capture scope. Do not infer
    # permission to match them, even if re-run.
    if final.get('schema_version') not in ('1.2','1.3') and request['consultation_type']!='academic': return review('Historical non-academic request needs coordinator review; scope was not confirmed.')
    route=routing_for(request); result['routing']=route; result['consultation_scope']=request['consultation_scope']
    if route=='support_review': return review('Institutional system issue: support or coordinator review required; no faculty allocated.')
    if route!='faculty_matching': return review('Coordinator review required; no relevant enrolled module or faculty consultation scope was confirmed.')
    result['topic_resolution']=request['topic_resolution']; result['urgency']=request['urgency']
    q=learner.qualification; module=learner.current_modules.get(code=request['module_code']); topic=AcademicTopic.objects.filter(code=request['topic_code'],module=module,is_active=True).first() if request['topic_code'] else None
    faculty=list(FacultyProfile.objects.prefetch_related('qualifications','modules_taught').order_by('faculty_id'))
    mappings={e.faculty_id:e for e in FacultyExpertise.objects.filter(module=module).prefetch_related('qualifications','catalogue_topics')}
    pref=key(request.get('preferred_faculty')); matched=[f.pk for f in faculty if pref and pref in {key(f.full_name),key(f.faculty_id)}]; preferred=matched[0] if len(matched)==1 else None
    if pref and pref not in ('any','anyone','flexible','nopreference','anyavailablefaculty'): result['preferred_faculty_status']='ambiguous' if len(matched)>1 else 'not_found' if not matched else 'ineligible'
    for f in faculty:
        e=mappings.get(f.pk); errors,exact=assess(f,e,q,module,topic,request,policy)
        if errors:
            result['excluded'].append({'faculty_id':f.faculty_id,'name':f.full_name,'reasons':errors}); continue
        taught=module.pk in {m.pk for m in f.modules_taught.all()}
        values={'module':LEVELS[e.expertise_level],'topic':(1 if exact else .5) if topic else None,'experience':min(f.teaching_experience_years/policy['experience_years'],1),'qualification':1 if taught else .8,'availability':None,'mode':None}
        score=academic_score(values,policy); is_pref=f.pk==preferred
        if is_pref: result['preferred_faculty_status']='eligible'
        reasons=['Approved direct module expertise ('+e.expertise_level+')','Approved qualification association','Compatible requested language and mode']
        reasons.append('Verified exact catalogue topic' if exact else 'General module expertise; exact topic not verified' if topic else 'No catalogue topic specified; topic score not assessed')
        if taught: reasons.append('Currently teaches requested module')
        if is_pref: reasons.append('Matches named faculty preference')
        result['candidates'].append({'faculty_id':f.faculty_id,'name':f.full_name,'department':f.department,'expertise_level':e.expertise_level,'match_type':'exact_topic' if exact else 'module_fallback' if topic else 'module_match','currently_teaching':taught,'preferred_faculty_match':is_pref,'languages':f.languages,'modes':f.consultation_modes,'teaching_years':f.teaching_experience_years,'reasons':reasons,'availability_status':'not_checked',**score})
    candidates=result['candidates']; candidates.sort(key=lambda c:(-c['academic_score'], -int(c['match_type']=='exact_topic'),-c['criteria']['module'],-int(c['currently_teaching']),c['faculty_id']))
    for i,c in enumerate(candidates,1): c['academic_rank']=i
    result['eligible_candidate_count']=len(candidates)
    # General module fallback is only shown if no strong/good exact candidate; low scores need review.
    ready=[c for c in candidates if c['academic_band']!='Review']; exact_ready=[c for c in ready if c['match_type']=='exact_topic']
    pool=exact_ready or ready
    # Named eligible preference can be included despite weaker topic fit, never below review threshold.
    pref_candidate=next((c for c in ready if c['preferred_faculty_match']),None)
    display=([pref_candidate]+[c for c in pool if c is not pref_candidate] if pref_candidate else pool)[:3]
    result['display_ids']=[c['faculty_id'] for c in display]
    if not display: return review('No eligible candidate meets the academic threshold; coordinator review required.')
    result['status']='academic_match_found';return result


def create_run(draft):
    row,policy=active_policy(); run=RecommendationRun(draft=draft,policy=row)
    result=calculate(draft,policy,row.pk if row else 'original-v1');result.update(recommendation_id=str(run.pk),generated_at=timezone.now().isoformat())
    run.result=result;run.save()
    if result['status']=='needs_review':
        from apps.coordinator.services import sync_case
        sync_case(draft.pk)
    return run

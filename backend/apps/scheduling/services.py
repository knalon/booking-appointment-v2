from datetime import timedelta
from django.utils import timezone
from apps.directory.models import FacultyProfile
from apps.matching.services import active_policy,calculate
from apps.matching.eligibility import key
from .models import FacultyWindow
from .booking import conflicts
from .preferences import DURATION, DAYS, search_preferences
from .slots import local_time,overlaps,slot_starts,within_working_hours,operational_score,MODES


def parse_preferences(draft,data):
    zone=draft.session.learner.time_zone
    windows=data.get('windows'); now=timezone.now()
    if not isinstance(windows,list) or len(windows)>DAYS: raise ValueError('Invalid scheduling windows.')
    result=[]
    for w in windows:
        a,b=local_time(w['start'],zone),local_time(w['end'],zone)
        kind=w.get('kind','preferred')
        if kind not in ('preferred','alternative') or a>=b or b>now+timedelta(days=DAYS+1) or b-a>timedelta(hours=25): raise ValueError('Invalid scheduling window.')
        if b<=now or (b-a==timedelta(minutes=DURATION) and a<now): continue
        result.append((max(a,now),b,kind))
    return result,DURATION,zone



def build(draft,data):
    windows,minutes,zone=parse_preferences(draft,data)
    row,policy=active_policy(); version=row.pk if row else 'original-v1'
    academic=calculate(draft,policy,version); req=draft.final_result['request']; mode=key(req.get('mode'))
    output={'schema_version':'1.0','request_id':str(draft.session_id),'policy_version':version,'policy':policy,'learner_time_zone':zone,'duration_minutes':minutes,'availability_checked':True,'booking_status':'not_booked','status':'no_slots','review_reason':academic.get('review_reason'),'candidates':[],'display_ids':[],'academic_candidates':len(academic['candidates']),'generated_at':timezone.now().isoformat(),'preferences':data}
    if not windows:
        output['review_reason']=academic.get('review_reason') or 'The requested time has passed or no longer fits a 30-minute consultation.'
        if not academic['candidates']: output['status']='needs_review'
        return output
    for c in academic['candidates']:
        f=FacultyProfile.objects.get(faculty_id=c['faculty_id']); supported={key(m) for m in f.consultation_modes}&MODES
        if mode!='either': supported &= {mode}
        records=list(FacultyWindow.objects.filter(faculty=f,active=True,start__lt=max(b for a,b,k in windows),end__gt=min(a for a,b,k in windows)))
        held=list(conflicts(min(a for a,b,k in windows),max(b for a,b,k in windows),f.pk,draft.session.learner_id).values_list('start','end'))
        busy=[w for w in records if w.kind=='busy']; available=[w for w in records if w.kind=='available']; found={}
        for a,b,kind in windows:
            for w in available:
                modes=supported if w.mode=='either' else supported&{w.mode}
                for start,end in compatible_starts(a,b,w,minutes):
                    if not within_working_hours(f,start,end) or any(overlaps(start,end,x.start,x.end) for x in busy) or any(overlaps(start,end,x,y) for x,y in held): continue
                    for m in sorted(modes):
                        score=1 if kind=='preferred' else .75
                        identity=(start.isoformat(),end.isoformat(),m)
                        if identity not in found or found[identity]['availability_value']<score:
                            found[identity]={'start':identity[0],'end':identity[1],'mode':m,'availability_value':score,'window_kind':kind}
        slots=sorted(found.values(),key=lambda s:(-s['availability_value'],s['start'],s['mode']))
        values=dict(c['criteria']); values['mode']=1 if slots else None; values['availability']=slots[0]['availability_value'] if slots else None
        scored=operational_score(values,policy) if slots else None
        candidate={**c,'criteria':values,'availability_status':'compatible' if slots else 'no_compatible_slot','slots':slots,'final_score':None,'final_band':None}
        if scored: candidate.update(final_score=scored['final_score'],final_band=scored['band'],final_points=scored['points'],final_maximum=scored['maximum'],final_contributions=scored['contributions'])
        output['candidates'].append(candidate)
    ready=[c for c in output['candidates'] if c['slots'] and c['academic_band']!='Review' and c['final_band']!='Review']
    exact=[c for c in ready if c['match_type']=='exact_topic']; pool=exact or ready
    if data.get('asap'):
        pool.sort(key=lambda c:(c['slots'][0]['start'],-int(c['preferred_faculty_match']),-c['final_score'],c['faculty_id']))
    else:
        pool.sort(key=lambda c:(-int(c['preferred_faculty_match']),-c['final_score'],c['slots'][0]['start'],c['faculty_id']))
    preferred=next((c for c in ready if c['preferred_faculty_match']),None)
    if preferred and not data.get('asap'): pool=[preferred]+[c for c in pool if c is not preferred]
    output['display_ids']=[c['faculty_id'] for c in pool[:3]]
    if pool: output.update(status='slots_found',review_reason=None)
    elif not academic['candidates']: output['status']='needs_review'
    else: output['review_reason']='No suitable candidate has compatible published slots meeting the policy. Start a new consultation with different preferences or request coordinator assistance.'
    return output


def compatible_starts(a,b,window,minutes):
    # Honor an exact learner start even if it is not on the 15-minute grid.
    if b-a==timedelta(minutes=minutes):
        if window.start<=a and b<=window.end: yield a,b
    else:
        yield from slot_starts(max(a,window.start),min(b,window.end),minutes)


def automatic_build(draft):
    zone=draft.session.learner.time_zone; now=timezone.now()
    final=dict(draft.final_result)
    if final.get('time_zone') and final['time_zone']!=zone: raise ValueError('Your time zone has changed. Start a new consultation to confirm your local time.')
    if not final.get('confirmed_at'):
        if not draft.confirmed_at: raise ValueError('The original confirmation date is missing. Start a new consultation.')
        final['confirmed_at']=draft.confirmed_at.isoformat()
    data=search_preferences(final,zone,now)
    result=build(draft,data)
    if result['status']=='no_slots' and result['academic_candidates']:
        alternative=build(draft,search_preferences(final,zone,now,alternative=True))
        if alternative['status']=='slots_found':
            alternative['alternative_offer']=True
            alternative['review_reason']='No suitable slots in your requested window. These are alternatives; choose one only if you are available then.'
            return alternative
    result['alternative_offer']=False
    return result

"""Canonical learner preferences and fixed-duration search windows.
No provider calls, database writes or locale-dependent date parsing.
"""
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DURATION = 30
DAYS = 30
WEEKDAYS = ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')
FLEX = {'flexible','any','anytime','any time','any day','whenever','no preference','either'}
ASAP = {'asap','as soon as possible','earliest available','earliest'}


def canonical_date(value, today):
    if not isinstance(value,str): raise ValueError('Specify a date or flexible.')
    s=value.strip().lower()
    if s in FLEX: return 'flexible'
    if s in ASAP: return 'asap'
    if s in ('today','tomorrow','day after tomorrow'):
        return (today+timedelta(days=('today','tomorrow','day after tomorrow').index(s))).isoformat()
    if s in WEEKDAYS or (s.startswith('this ') and s[5:] in WEEKDAYS):
        day=WEEKDAYS.index(s.removeprefix('this ')); return (today+timedelta(days=(day-today.weekday())%7)).isoformat()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',s): raise ValueError('Use an exact date, such as 2026-12-01, or flexible.')
    d=date.fromisoformat(s)
    if d<today or d>=today+timedelta(days=DAYS): raise ValueError('Choose a date within the next 30 days.')
    return d.isoformat()


def clock(s):
    m=re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',s.strip())
    if not m: raise ValueError('Use a time such as 14:00 or 2 PM.')
    h=int(m[1]); minute=int(m[2] or 0)
    if m[3]:
        if not 1<=h<=12: raise ValueError('Invalid time.')
        h=h%12+(12 if m[3]=='pm' else 0)
    elif m[2] is None: raise ValueError('Specify AM/PM or a 24-hour time.')
    if not 0<=h<24 or not 0<=minute<60: raise ValueError('Invalid time.')
    return h*60+minute


def hhmm(n): return f'{n//60:02d}:{n%60:02d}'


def canonical_time(value):
    if not isinstance(value,str): raise ValueError('Specify a time or flexible.')
    s=' '.join(value.strip().lower().replace('–','-').replace('—','-').split())
    if s in FLEX: return 'flexible'
    if s in ASAP: return 'asap'
    periods={'morning':'09:00-12:00','afternoon':'12:00-17:00','evening':'17:00-21:00'}
    if s in periods: return periods[s]
    if s.startswith(('after ','from ')) and not re.search(r'\s(?:to|until)\s|-',s):
        return 'after '+hhmm(clock(s.split(' ',1)[1]))
    if s.startswith('before '): return 'before '+hhmm(clock(s[7:]))
    s=s.removeprefix('between ').removeprefix('from ')
    parts=re.split(r'\s*(?:-|\bto\b|\buntil\b|\band\b)\s*',s)
    if len(parts)==2:
        a,b=map(clock,parts)
        if b-a<DURATION: raise ValueError('Time range must fit 30 minutes on the same day.')
        return hhmm(a)+'-'+hhmm(b)
    if len(parts)!=1: raise ValueError('Specify one time or range.')
    return 'at '+hhmm(clock(s.removeprefix('at ')))


def bounds(value):
    v=canonical_time(value)
    if v in ('flexible','asap'): return 0,1440
    if v.startswith('after '): a,b=clock(v[6:]),1440
    elif v.startswith('before '): a,b=0,clock(v[7:])
    elif v.startswith('at '): a=clock(v[3:]); b=a+DURATION
    else: a,b=map(clock,v.split('-'))
    if b>1440 or b-a<DURATION: raise ValueError('Choose a time allowing 30 minutes before midnight.')
    return a,b


def intake_preferences(data, zone, now=None):
    """Invalid/ambiguous preferences stay missing; no silent broadening."""
    today=(now or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone)).date()
    out=dict(data)
    try: out['preferred_date']=canonical_date(out.get('preferred_date'),today)
    except (ValueError,TypeError): out['preferred_date']=None
    try:
        out['preferred_time']=canonical_time(out.get('preferred_time')); bounds(out['preferred_time'])
    except (ValueError,TypeError): out['preferred_time']=None
    if out['preferred_date']=='asap' and not data.get('preferred_time'): out['preferred_time']='flexible'
    return out


def search_preferences(final, zone, now, alternative=False):
    """Anchor old relative preferences to original confirmation, not today."""
    req=final['request']; tz=ZoneInfo(zone); today=now.astimezone(tz).date()
    stamp=datetime.fromisoformat(final['confirmed_at']); anchor=stamp.astimezone(tz).date()
    d=canonical_date(req.get('preferred_date'),anchor); t=canonical_time(req.get('preferred_time'))
    a,b=bounds(t)
    if alternative or d in ('flexible','asap'):
        days=[today+timedelta(days=i) for i in range(DAYS)]
    else: days=[date.fromisoformat(d)]
    if alternative: a,b=0,1440
    windows=[]
    for day in days:
        if not today<=day<today+timedelta(days=DAYS): continue
        start=datetime.combine(day,time.min)+timedelta(minutes=a)
        end=datetime.combine(day,time.min)+timedelta(minutes=b)
        if end.replace(tzinfo=tz).astimezone(timezone.utc)<=now: continue
        windows.append({'start':start.isoformat(timespec='minutes'),'end':end.isoformat(timespec='minutes'),'kind':'alternative' if alternative else 'preferred'})
    return {'windows':windows,'duration_minutes':DURATION,'automatic':True,'alternative_offer':alternative,'asap':d=='asap' or t=='asap'}

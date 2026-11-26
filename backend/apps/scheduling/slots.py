from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal

MODES={'online','facetoface'}
def local_time(value, zone):
    dt=datetime.fromisoformat(value)
    if dt.tzinfo is not None: raise ValueError('Enter local date and time without an offset.')
    tz=ZoneInfo(zone)
    a,b=dt.replace(tzinfo=tz,fold=0),dt.replace(tzinfo=tz,fold=1)
    if a.utcoffset()!=b.utcoffset(): raise ValueError('Ambiguous or nonexistent local time; choose another time.')
    return a.astimezone(timezone.utc)

def overlaps(a,b,c,d): return a<d and c<b

def slot_starts(start,end,minutes):
    step=timedelta(minutes=15); duration=timedelta(minutes=minutes)
    # Grid anchored to UTC quarter-hour; never round down.
    start=datetime.fromtimestamp(__import__("math").ceil(start.timestamp()/900)*900,timezone.utc)
    while start+duration<=end:
        yield start,start+duration
        start+=step

def within_working_hours(f,start,end):
    tz=ZoneInfo(f.time_zone); a,b=start.astimezone(tz),end.astimezone(tz)
    return bool(f.working_hours_start and f.working_hours_end and a.date()==b.date() and a.strftime('%A') in f.working_days and f.working_hours_start<=a.time() and b.time()<=f.working_hours_end)

def operational_score(criteria,policy):
    weights=policy['weights']; keys=[k for k in weights if criteria.get(k) is not None]
    raw=sum((Decimal(str(criteria[k]))*weights[k] for k in keys),Decimal(0)); maximum=sum(weights[k] for k in keys)
    from decimal import ROUND_HALF_UP
    score=float((raw*100/maximum).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    return {'final_score':score,'points':float(raw),'maximum':maximum,'band':'Strong' if score>=policy['strong'] else 'Good' if score>=policy['good'] else 'Review','contributions':{k:float(Decimal(str(criteria[k]))*weights[k]) if k in keys else None for k in weights}}

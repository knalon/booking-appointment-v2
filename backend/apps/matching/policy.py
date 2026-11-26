from decimal import Decimal, ROUND_HALF_UP

DEFAULT = {'weights': {'module':30,'topic':25,'experience':15,'qualification':10,'availability':15,'mode':5}, 'experience_years':10,'strong':85,'good':70,'allow_module_fallback':True}
LEVELS={'Expert':1,'Advanced':0.85,'Intermediate':0.70,'Basic':0.55}
ACADEMIC=('module','topic','experience','qualification')

def validate_policy(data):
    if not isinstance(data,dict) or set(data)!=set(DEFAULT): raise ValueError('Invalid policy fields.')
    w=data['weights']
    if not isinstance(w,dict) or set(w)!=set(DEFAULT['weights']) or any(type(v) is not int or not 0<=v<=100 for v in w.values()) or sum(w.values())!=100: raise ValueError('Weights must be whole numbers totaling 100.')
    if w['module']<=0: raise ValueError('Module weight must be positive.')
    if type(data['experience_years']) is not int or not 1<=data['experience_years']<=50: raise ValueError('Experience benchmark must be 1–50 years.')
    if any(type(data[k]) is not int for k in ('strong','good')) or not 0<data['good']<data['strong']<=100: raise ValueError('Require 0 < good < strong ≤ 100.')
    if type(data['allow_module_fallback']) is not bool: raise ValueError('Invalid fallback policy.')
    return data

def rounded(x): return float(Decimal(str(x)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))

def academic_score(values,policy):
    w=policy['weights']; assessed=[k for k in ACADEMIC if values.get(k) is not None]
    points={k:rounded(Decimal(str(values[k]))*w[k]) if k in assessed else None for k in w}
    # Score against applicable academic weight only; availability and mode remain pending.
    raw=sum((Decimal(str(values[k]))*w[k] for k in assessed),Decimal(0)); maximum=sum(w[k] for k in assessed)
    score=rounded(raw*100/maximum)
    band='Strong' if score>=policy['strong'] else 'Good' if score>=policy['good'] else 'Review'
    return {'criteria':values,'contributions':points,'academic_points':rounded(raw),'academic_maximum':maximum,'academic_score':score,'academic_band':band,'final_score':None}

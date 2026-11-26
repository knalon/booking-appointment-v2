"""Deterministic clarification and explicit confirmation. No provider calls here."""
import re
import unicodedata
from .policy import missing, normalize_draft
from .routing import canonical_language

QUESTIONS = {
    'consultation_type': ('What kind of consultation do you need: academic, technical or other support?', 'ပညာရေး၊ နည်းပညာ၊ အခြားအကူအညီ ဘယ်လိုဆွေးနွေးမှု လိုပါသလဲ?', '您需要哪类咨询：学业、技术还是其他支持？'),
    'consultation_scope': ('Is this about your coursework or project, or an institutional system you cannot access?', 'သင်၏ သင်ခန်းစာ သို့မဟုတ် project နှင့် သက်ဆိုင်ပါသလား၊ ကျောင်းစနစ် အသုံးပြု၍မရခြင်းလား?', '这是您的课程或项目问题，还是无法使用学校系统的问题？'),
    'difficulty': ('What would you like help with?', 'ဘာအကြောင်းအရာကို အကူအညီလိုပါသလဲ?', '您希望获得哪方面的帮助？'),
    'module_code': ('Which of your enrolled modules is this about?', 'သင်တက်နေသော ဘယ်ဘာသာရပ်နဲ့ သက်ဆိုင်ပါသလဲ?', '这涉及您已修读的哪门课程？'),
    'topic_resolution': ('Which topic in this module best describes your difficulty, or is none suitable?', 'ဒီဘာသာရပ်ထဲက ဘယ်ခေါင်းစဉ်နဲ့ အကိုက်ညီဆုံးလဲ၊ ဒါမှမဟုတ် ကိုက်ညီတာမရှိဘူးလား?', '本课程中哪个主题最符合您的困难，还是没有合适的主题？'),
    'urgency': ('Is this urgent, or is a routine consultation suitable?', 'အရေးတကြီး လိုအပ်ပါသလား၊ ပုံမှန်ဆွေးနွေးမှုနဲ့ အဆင်ပြေပါသလား?', '您需要紧急咨询，还是普通咨询即可？'),
    'preferred_date': ('What date would you prefer (within 30 days), or are you flexible?', 'ဘယ်နေ့ကို ပိုနှစ်သက်ပါသလဲ၊ ရက်အဆင်ပြေသလို ရပါသလား?', '您希望哪一天咨询，还是日期不限？'),
    'preferred_time': ('What time or time range works for you (for example 2 PM, afternoon or flexible)?', 'ဘယ်အချိန် သို့မဟုတ် အချိန်အပိုင်းအခြား အဆင်ပြေပါသလဲ?', '什么时间或时间段适合您？'),
    'mode': ('Would you prefer online, face-to-face, or either?', 'အွန်လိုင်း၊ လူကိုယ်တိုင်၊ နှစ်မျိုးလုံးအဆင်ပြေ — ဘယ်ပုံစံကို ရွေးမလဲ?', '您希望线上、面对面，还是两种方式都可以？'),
    'preferred_language': ('Which consultation language works for you (English, Myanmar, Chinese, or any acceptable alternatives)?', 'ဆွေးနွေးမှုအတွက် ဘယ်ဘာသာစကားကို ပိုနှစ်သက်ပါသလဲ?', '您希望使用哪种语言进行咨询？'),
    'qualification': ('Your active qualification could not be verified. Please contact your coordinator.', 'သင့် qualification ကို အတည်မပြုနိုင်ပါ။ Coordinator ကို ဆက်သွယ်ပါ။', '无法验证您的有效资格课程，请联系协调员。'),
}
LANGS=('en','my','zh')
ORDER=('qualification','difficulty','consultation_type','consultation_scope','module_code','topic_resolution','urgency','preferred_date','preferred_time','mode','preferred_language')

def target(draft, context):
    absent=missing(draft,context)
    return next((k for k in ORDER if k in absent),None)

def question(key, draft, context, lang='en'):
    text=QUESTIONS[key][LANGS.index(lang)]
    if key=='module_code' and draft.get('consultation_type')=='technical':
        text=('Which enrolled module best relates to your project problem, or is none suitable?', 'သင့် project ပြဿနာနှင့် ကိုက်ညီသော သင်ခန်းစာ ရှိပါသလား၊ မရှိဘူးလား?', '哪个已修读的课程与您的项目问题最相关，还是没有合适的课程？')[LANGS.index(lang)]
    if key=='module_code':
        choices=[m['name'] for m in context['modules']]
    elif key=='topic_resolution':
        choices=[t['name'] for m in context['modules'] if m['code']==draft.get('module_code') for t in m['topics']]
    else: choices=[]
    return text+ ('\n'+' · '.join(choices) if choices else '')

def summary(draft, context, lang='en'):
    draft=normalize_draft(draft)
    if context.get('schedule_intake'):
        from apps.scheduling.preferences import intake_preferences
        draft=intake_preferences(draft,context['time_zone'])
    idx=LANGS.index(lang)
    module=next((m for m in context['modules'] if m['code']==draft.get('module_code')),None)
    topic=next((t['name'] for t in (module or {}).get('topics',[]) if t['code']==draft.get('topic_code')),None)
    flexible=('Flexible','အဆင်ပြေသလို','不限')[idx]
    unspecified=('Not specified','မသတ်မှတ်ထားပါ','未指定')[idx]
    def val(v): return flexible if v=='flexible' else str(v) if v is not None else unspecified
    rows=[(('Consultation type','ဆွေးနွေးမှုအမျိုးအစား','咨询类型'),draft.get('consultation_type')),
          (('Consultation scope','ဆွေးနွေးမှု နယ်ပယ်','咨询范围'),{'coursework':('Coursework','သင်ခန်းစာ','课程学习'),'learner_project':('Learner project','သင်ယူသူ project','学员项目'),'institutional_system':('Institutional system','ကျောင်းစနစ်','学校系统'),'administrative':('Administrative','စီမံရေးရာ','行政事务')}.get(draft.get('consultation_scope'),(None,None,None))[idx]),
          (('Module','ဘာသာရပ်','课程'),(module or {}).get('name')),
          (('Catalogue topic','ခေါင်းစဉ်','主题'),topic),
          (('Difficulty','အခက်အခဲ','困难'),draft.get('difficulty')),
          (('Preferred faculty','ဆရာ/ဆရာမ','意向教师'),draft.get('preferred_faculty') or ('No specific preference recorded','သီးခြားရွေးချယ်မှု မရှိသေးပါ','未记录指定教师')[idx]),
          (('Date','ရက်စွဲ','日期'),draft.get('preferred_date')),
          (('Time','အချိန်','时间'),draft.get('preferred_time')),
          (('Duration','ကြာချိန်','时长'),flexible if draft.get('duration_preference')=='flexible' else str(draft.get('duration_minutes'))+' min'),
          (('Mode','ပုံစံ','方式'),draft.get('mode')),
          (('Language','ဘာသာစကား','语言'),draft.get('preferred_language')),
          (('Urgency','အရေးတကြီး လိုအပ်မှု','紧急程度'),draft.get('urgency'))]
    if draft.get('urgency_reason'): rows.append((('Deadline / reason','သတ်မှတ်ရက် / အကြောင်းရင်း','截止日期 / 原因'),draft['urgency_reason']))
    heading=('Your consultation summary','သင့်ဆွေးနွေးမှု အကျဉ်းချုပ်','您的咨询摘要')[idx]
    footer=('Are these details correct? You can reply Yes, correct or use Confirm request. No appointment is booked yet.', 'အချက်အလက်တွေ မှန်ကန်ပါသလား? ဟုတ်ပါတယ် ဟု ပြန်ဖြေနိုင်သလို Confirm request ကိုလည်း နှိပ်နိုင်ပါတယ်။ ရက်ချိန်းမသတ်မှတ်ရသေးပါ။', '以上信息正确吗？您可以回复“对的”或点击确认请求。尚未预约。')[idx]
    return heading+'\n\n'+'\n'.join(labels[idx]+': '+val(value) for labels,value in rows)+'\n\n'+footer

def normalized(text):
    text=unicodedata.normalize('NFKC',text).casefold().replace('’',"'")
    return re.sub(r'\s+',' ',re.sub(r'[.,!。！？，၊။]+',' ',text)).strip()

AFFIRMATIONS={normalized(x) for x in ('yes','yes correct','yes that is correct',"yes that's correct",'correct',"that's right",'that is right',"that's correct",'exactly','looks good','everything is correct','okay proceed','ok proceed','yes please confirm','ဟုတ်ပါတယ်','မှန်ပါတယ်','ဟုတ်ကဲ့','对的','正确','是的','没问题','对的，没问题')}

def summary_language(last, draft, context):
    if target(draft,context): return None
    return next((lang for lang in LANGS if last==summary(draft,context,lang)),None)

def affirmative(text): return normalized(text) in AFFIRMATIONS

def short_answer(last, text, draft, context):
    """Only unambiguous whole-message answers to our exact previous question."""
    key=target(draft,context)
    if not key or not any(last==question(key,draft,context,lang) for lang in LANGS): return None
    n=normalized(text)
    flexible={'any','anytime','whenever','flexible','no preference','not sure',"i don't know",'no idea','不限','随便','အဆင်ပြေသလို'}
    if key=='urgency':
        if n in {'no','not really','not urgent','routine','normal','no rush','不急','普通','မလိုပါ','အရေးမကြီးပါ'}: return {'urgency':'normal','urgency_reason':None}
        if n in {'urgent','very urgent','紧急','အရေးကြီးပါတယ်'}: return {'urgency':'urgent','urgency_reason':None}
    if key=='mode':
        modes={'online':'online','face to face':'face_to_face','face-to-face':'face_to_face','in person':'face_to_face','either':'either','both':'either','线上':'online','线下':'face_to_face','都可以':'either','အွန်လိုင်း':'online','လူကိုယ်တိုင်':'face_to_face'}
        if n in modes: return {'mode':modes[n]}
    if key=='preferred_language':
        languages={'english':'English','myanmar':'Myanmar','burmese':'Myanmar','chinese':'Chinese','英语':'English','中文':'Chinese','缅甸语':'Myanmar','မြန်မာ':'Myanmar','အင်္ဂလိပ်':'English'}
        if n in languages: return {'preferred_language':languages[n]}
        try: return {'preferred_language':canonical_language(text)}
        except ValueError: pass
    if key in ('preferred_date','preferred_time') and n in flexible-{'not sure',"i don't know",'no idea'}: return {key:'flexible'}
    if key in ('preferred_date','preferred_time') and context.get('schedule_intake'):
        from apps.scheduling.preferences import canonical_date, canonical_time, bounds
        from datetime import datetime
        from zoneinfo import ZoneInfo
        try:
            if key=='preferred_date':
                value=canonical_date(text,datetime.now(ZoneInfo(context['time_zone'])).date())
                if value=='asap' and not draft.get('preferred_time'): return {key:value,'preferred_time':'flexible'}
            else:
                value=canonical_time(text); bounds(value)
            return {key:value}
        except ValueError: pass
    if key=='consultation_type' and n in ('academic','technical','other'): return {key:n,'consultation_scope':None}
    if key=='consultation_scope':
        scopes={'coursework':'coursework','my coursework':'coursework','project':'learner_project','my project':'learner_project','my final project':'learner_project','final project':'learner_project','institutional system':'institutional_system','school system':'institutional_system','lms':'institutional_system'}
        if n in scopes: return {'consultation_scope':scopes[n]}
    if key=='module_code' and draft.get('consultation_type')=='technical' and n in {'none','none of these','no suitable module','not related to a module'}: return {'module_code':None,'topic_code':None,'topic_resolution':'no_match'}
    return None

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.directory.models import LearnerProfile
from .models import ConversationSession, ConversationMessage, ConsultationDraft
from .policy import RULES, FIELDS, limits, catalogue, clean_draft, missing, expired, normalize_draft
from .service import configuration, converse, NLPError
from .controller import affirmative, summary_language, summary
from .routing import routing_for, language_options

class TurnThrottle(UserRateThrottle):
    scope='conversation_turn'
    def get_rate(self): return f"{limits()['rate']}/min"

def profiles(user):
    qs=LearnerProfile.objects.filter(status='Active')
    if not settings.DEBUG or user.is_staff or user.is_superuser: return qs.none()
    return qs.filter(user=user)

def session_for(user,pk,lock=False):
    qs=ConversationSession.objects.filter(owner=user,learner__in=profiles(user))
    return get_object_or_404(qs.select_for_update() if lock else qs,pk=pk)

def intake_context(learner):
    return {**catalogue(learner),'schedule_intake':True}

def state(s):
    ctx=intake_context(s.learner) if s.status=='active' else catalogue(s.learner); data=normalize_draft(s.draft.data)
    absent=missing(data,ctx,legacy=s.status=='confirmed' and (s.draft.final_result or {}).get('schema_version') not in ('1.1','1.2','1.3'))
    try: data=clean_draft(data,ctx)
    except ValueError: absent=absent+['academic_selection_needs_review']
    if s.status=='confirmed' and s.draft.final_result:
        data=s.draft.final_result['request']  # Preserve historical display, including old durations.
    last=s.messages.filter(role='assistant').last()
    shown=summary_language(last.content,data,ctx) if last and not absent and s.status=='active' else None
    return {'id':str(s.pk),'learner_id':s.learner.learner_id,'status':s.status,'turns':s.turns,'chat_closed':s.status!='active' or expired(s) or s.turns>=limits()['max_turns'],'draft':data,'final_result':s.draft.final_result,'missing':absent,'confirmation_summary':summary(data,ctx,shown or 'en') if not absent and s.status=='active' else None,'summary_in_chat':bool(shown),'context':ctx,'messages':list(s.messages.values('role','content','created_at')),'usage':{'input_tokens':s.input_tokens,'output_tokens':s.output_tokens}}

class Base(APIView):
    permission_classes=[IsAuthenticated]
    def initial(self, request, *args, **kwargs):
        super().initial(request,*args,**kwargs)
        if not profiles(request.user).exists(): raise PermissionDenied('Conversation access is restricted to active learner accounts in development.')
class Status(Base):
    def get(self,request):
        key,model=configuration()
        return Response({'configured':bool(key),'model':model,'limits':limits(),'rules':RULES,'staff_preview':False,'learners':list(profiles(request.user).values('learner_id','full_name'))})
class Sessions(Base):
    def get(self,request):
        return Response(list(ConversationSession.objects.filter(owner=request.user,learner__in=profiles(request.user)).order_by('-updated_at').values('id','learner__learner_id','status','turns','updated_at')[:100]))
    @transaction.atomic
    def post(self,request):
        if request.data.get('accepted_rules') is not True: raise ValidationError('Accept the conversation rules first.')
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        learner=get_object_or_404(profiles(request.user),learner_id=request.data.get('learner_id'))
        existing=ConversationSession.objects.filter(owner=request.user,learner=learner,status='active').first()
        if existing: return Response({'detail':'Resume or close the existing conversation first.'},status=409)
        s=ConversationSession.objects.create(owner=request.user,learner=learner)
        ConsultationDraft.objects.create(session=s,data=normalize_draft({k:None for k in FIELDS}))
        return Response(state(s),status=201)
class SessionDetail(Base):
    def get(self,request,pk): return Response(state(session_for(request.user,pk)))
    @transaction.atomic
    def patch(self,request,pk):
        s=session_for(request.user,pk,True)
        if s.status!='active': raise ValidationError('This conversation is closed.')
        action=request.data.get('action')
        if action=='close': s.status='closed'; s.save(update_fields=['status']); return Response(state(s))
        if action not in ('edit','confirm'): raise ValidationError('Unknown action.')
        ctx=intake_context(s.learner)
        try: data=clean_draft(request.data.get('draft'),ctx)
        except ValueError as e: raise ValidationError(str(e)) from None
        if action=='confirm' and missing(data,ctx): raise ValidationError('Complete all required fields before confirming.')
        s.draft.data=data
        if action=='confirm':
            s.draft.confirmed_at=timezone.now();s.draft.final_result=build_result(s,data,ctx);s.status='confirmed';s.save(update_fields=['status'])
        s.draft.save()
        return Response(state(s))
class Turn(Base):
    throttle_classes=[TurnThrottle]
    @transaction.atomic
    def post(self,request,pk):
        s=session_for(request.user,pk,True); lim=limits()
        if s.status!='active' or expired(s) or s.turns>=lim['max_turns']: raise ValidationError('Chat closed. Complete the draft manually or close the session.')
        text=request.data.get('message')
        if not isinstance(text,str) or not text.strip() or len(text)>lim['max_length']: raise ValidationError('Enter a message within the length limit.')
        text=text.strip(); context=intake_context(s.learner)
        history=list(s.messages.values('role','content'))+[{'role':'user','content':text}]
        # Bound serialized context; no automatic attachment of other sessions.
        if sum(len(m['content']) for m in history)>100000: raise ValidationError('History limit reached; use manual entry.')
        # Only a clear affirmation immediately after the exact current server summary
        # can confirm via chat. Corrections and stale summaries never confirm.
        draft=normalize_draft(s.draft.data)
        last=history[-2]['content'] if len(history)>1 and history[-2]['role']=='assistant' else ''
        lang=summary_language(last,draft,context)
        if lang and affirmative(text):
            try: data=clean_draft(draft,context)
            except ValueError as e: raise ValidationError(str(e)) from None
            if missing(data,context): raise ValidationError('Complete all required fields before confirming.')
            s.draft.data=data; s.draft.confirmed_at=timezone.now(); s.draft.final_result=build_result(s,data,context); s.draft.save()
            reply={'en':'Request confirmed. No appointment has been booked.','my':'ဆွေးနွေးမှုလိုအပ်ချက် အတည်ပြုပြီးပါပြီ။ ရက်ချိန်းမသတ်မှတ်ရသေးပါ။','zh':'咨询需求已确认，尚未预约。'}[lang]
            ConversationMessage.objects.bulk_create([ConversationMessage(session=s,role='user',content=text),ConversationMessage(session=s,role='assistant',content=reply)])
            s.turns+=1; s.status='confirmed'; s.save()
            return Response(state(s))
        try: result,inp,out=converse(history,normalize_draft(s.draft.data),context,s.turns+1)
        except NLPError as e: return Response({'detail':str(e)},status=e.status)
        ConversationMessage.objects.bulk_create([ConversationMessage(session=s,role='user',content=text),ConversationMessage(session=s,role='assistant',content=result['assistant_message'])])
        # Unrelated messages consume a turn but cannot modify the saved draft.
        if result.get('relevance')!='unrelated':
            s.draft.data=result['draft'];s.draft.save(update_fields=['data'])
        s.turns+=1;s.input_tokens+=inp;s.output_tokens+=out;s.save()
        return Response(state(s))

from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
import json
@csrf_protect
@require_POST
def learner_login(request):
    try:
        data=json.loads(request.body);user=authenticate(request,username=data['username'],password=data['password'])
    except (ValueError,KeyError,TypeError): user=None
    if not user or not user.is_active or not profiles(user).exists(): return JsonResponse({'detail':'Invalid credentials or no linked learner profile.'},status=403)
    login(request,user)
    return JsonResponse({'username':user.get_username(),'csrfToken':get_token(request)})


def build_result(s,data,ctx):
    topic_name=next((t['name'] for m in ctx['modules'] if m['code']==data['module_code'] for t in m['topics'] if t['code']==data['topic_code']),None)
    return {'schema_version':'1.3','routing':routing_for(data),'preferred_languages':language_options(data['preferred_language']),'language_match_policy':'any','resolved_topic_name':topic_name,'request_id':str(s.pk),'status':'request_confirmed','learner_id':s.learner.learner_id,'qualification_code':ctx['qualification']['code'],'time_zone':ctx['time_zone'],'confirmed_at':s.draft.confirmed_at.isoformat(),'request':data.copy(),'booking_status':'not_booked'}

class ConfirmedResults(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        if not request.user.is_staff: raise PermissionDenied('Management access required.')
        qs=ConsultationDraft.objects.filter(session__status='confirmed',final_result__isnull=False).exclude(session__owner__is_staff=True).order_by('-confirmed_at')[:100]
        return Response([d.final_result for d in qs])

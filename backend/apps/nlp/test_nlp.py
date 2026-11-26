from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.directory.models import Qualification, AcademicModule, QualificationModule, AcademicTopic, LearnerProfile
from .policy import FIELDS
from .models import ConversationSession

@override_settings(DEBUG=True)
class ConversationTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='learner',password='testpass123')
        q=Qualification.objects.create(code='Q',name='Test qualification')
        m=AcademicModule.objects.create(code='M',name='Test module')
        QualificationModule.objects.create(qualification=q,module=m)
        AcademicTopic.objects.create(code='T',name='Test topic',module=m)
        p=LearnerProfile.objects.create(user=self.user,learner_id='L',full_name='Test Learner',email='test@example.org',qualification=q)
        p.current_modules.add(m)
        self.client=APIClient();self.client.force_authenticate(self.user)
        self.base='/api/nlp/sessions/'
    def start(self):
        r=self.client.post(self.base,{'learner_id':'L','accepted_rules':True},format='json');self.assertEqual(r.status_code,201);return self.base+r.data['id']+'/'
    def test_rules_required(self):
        self.assertEqual(self.client.post(self.base,{'learner_id':'L'},format='json').status_code,400)
    def test_history_and_limit(self):
        path=self.start();draft={k:None for k in FIELDS};draft.update(module_code='M',difficulty='Loops')
        with patch('apps.nlp.views.converse',return_value=({'assistant_message':'When?', 'draft':draft},20,10)) as call:
            self.assertEqual(self.client.post(path+'turn/',{'message':'Loops'},format='json').status_code,200)
            r=self.client.post(path+'turn/',{'message':'Tomorrow'},format='json');self.assertEqual(r.status_code,200);self.assertEqual(len(call.call_args.args[0]),3);self.assertEqual(r.data['turns'],2)
            ConversationSession.objects.update(turns=30)
            self.assertEqual(self.client.post(path+'turn/',{'message':'Again'},format='json').status_code,400)
    def test_wrong_topic_and_incomplete_confirm(self):
        path=self.start();d={k:None for k in FIELDS};d.update(module_code='M',topic_code='FAKE')
        self.assertEqual(self.client.patch(path,{'action':'edit','draft':d},format='json').status_code,400)
        d['topic_code']=None
        self.assertEqual(self.client.patch(path,{'action':'confirm','draft':d},format='json').status_code,400)
    def test_owner_isolation(self):
        path=self.start();other=get_user_model().objects.create_user(username='other');self.client.force_authenticate(other)
        self.assertEqual(self.client.get(path).status_code,403)
    def test_confirm_without_booking(self):
        path=self.start();d={k:None for k in FIELDS};d.update(consultation_type='academic',module_code='M',topic_code='T',difficulty='Loops',preferred_date='flexible',preferred_time='flexible',duration_minutes=30,duration_preference='fixed',mode='online',preferred_language='English',urgency='normal',topic_resolution='exact')
        r=self.client.patch(path,{'action':'confirm','draft':d},format='json');self.assertEqual(r.status_code,200);self.assertEqual(r.data['status'],'confirmed')

    def test_flexible_duration_replaced_by_fixed_30_and_final_result(self):
        path=self.start();d={k:None for k in FIELDS};d.update(consultation_type='academic',module_code='M',difficulty='Loops',preferred_date='flexible',preferred_time='flexible',duration_preference='flexible',mode='online',preferred_language='English',urgency='normal',topic_resolution='no_match')
        r=self.client.patch(path,{'action':'confirm','draft':d},format='json');self.assertEqual(r.status_code,200)
        self.assertEqual(r.data['final_result']['request']['duration_preference'],'fixed');self.assertEqual(r.data['final_result']['request']['duration_minutes'],30)
        self.assertEqual(self.client.get(path).data['final_result'],r.data['final_result'])
        self.assertEqual(self.client.patch(path,{'action':'edit','draft':d},format='json').status_code,400)
    def test_staff_no_chat(self):
        staff=get_user_model().objects.create_user(username='staff',is_staff=True);self.client.force_authenticate(staff)
        self.assertEqual(self.client.get('/api/nlp/status/').status_code,403)
        self.assertEqual(self.client.post(self.base,{'learner_id':'L','accepted_rules':True},format='json').status_code,403)

    def test_unknown_duration_defaults_to_fixed_30(self):
        path=self.start();d={k:None for k in FIELDS};d.update(consultation_type='academic',module_code='M',difficulty='Loops',preferred_date='flexible',preferred_time='flexible',mode='online',preferred_language='English',urgency='normal',topic_resolution='no_match')
        r=self.client.patch(path,{'action':'confirm','draft':d},format='json');self.assertEqual(r.status_code,200);self.assertEqual(r.data['final_result']['request']['duration_minutes'],30)
    def test_provision_idempotent(self):
        from django.core.management import call_command
        from io import StringIO
        q=Qualification.objects.get(code='Q')
        p=LearnerProfile.objects.create(learner_id='L2',full_name='Alex Tan',email='l2@example.invalid',qualification=q)
        call_command('provision_demo_learners',confirm='DEMO-ONLY',stdout=StringIO());p.refresh_from_db()
        self.assertEqual(p.user.username,'alextan');self.assertTrue(p.user.check_password('1234'));self.assertFalse(p.user.is_staff)
        old=p.user.password;call_command('provision_demo_learners',confirm='DEMO-ONLY',stdout=StringIO());p.refresh_from_db();self.assertEqual(p.user.password,old)

    def test_urgency_and_topic_resolution_required(self):
        path=self.start();d={k:None for k in FIELDS};d.update(consultation_type='academic',module_code='M',difficulty='Abstraction',preferred_date='flexible',preferred_time='flexible',duration_preference='flexible',mode='online',preferred_language='English')
        self.assertEqual(self.client.patch(path,{'action':'confirm','draft':d},format='json').status_code,400)
        d['urgency']='urgent';d['urgency_reason']='Assignment tomorrow'
        self.assertEqual(self.client.patch(path,{'action':'confirm','draft':d},format='json').status_code,400)
        d.update(topic_code='T',topic_resolution='broader')
        r=self.client.patch(path,{'action':'confirm','draft':d},format='json');self.assertEqual(r.status_code,200)
        self.assertEqual(r.data['final_result']['schema_version'],'1.3');self.assertEqual(r.data['final_result']['resolved_topic_name'],'Test topic');self.assertEqual(r.data['final_result']['request']['urgency_reason'],'Assignment tomorrow')
    def test_unrelated_turn_preserves_draft(self):
        path=self.start();before=self.client.get(path).data['draft'];changed=dict(before,difficulty='Movie recommendation')
        with patch('apps.nlp.views.converse',return_value=({'assistant_message':'Consultations only.', 'draft':changed,'relevance':'unrelated'},10,5)):
            r=self.client.post(path+'turn/',{'message':'Recommend a movie'},format='json')
        self.assertEqual(r.status_code,200);self.assertEqual(r.data['draft'],before);self.assertEqual(r.data['turns'],1)

    def ready_draft(self):
        d={k:None for k in FIELDS}
        d.update(consultation_type='academic',module_code='M',difficulty='Understanding functional programming in Python',topic_resolution='no_match',preferred_date='tomorrow',preferred_time='afternoon',duration_preference='flexible',mode='online',preferred_language='English',urgency='normal')
        return d

    def test_contextual_short_answers(self):
        from .controller import question, target, short_answer
        from .policy import catalogue
        ctx=catalogue(LearnerProfile.objects.get(learner_id='L'))
        for field,text,expected in [('urgency','Not really',{'urgency':'normal','urgency_reason':None}),('mode','Online',{'mode':'online'}),('preferred_language','English',{'preferred_language':'English'})]:
            d=self.ready_draft();d[field]=None
            self.assertEqual(target(d,ctx),field)
            q=question(field,d,ctx)
            self.assertEqual(q.count('?'),1)
            self.assertEqual(short_answer(q,text,d,ctx),expected)
            self.assertIsNone(short_answer(q,text+' and recommend a movie',d,ctx))

    def test_yes_correct_after_summary(self):
        from .controller import summary
        from .views import intake_context
        from .models import ConversationMessage
        path=self.start();d=self.ready_draft()
        self.assertEqual(self.client.patch(path,{'action':'edit','draft':d},format='json').status_code,200)
        s=ConversationSession.objects.get();ctx=intake_context(s.learner)
        ConversationMessage.objects.create(session=s,role='assistant',content=summary(d,ctx))
        with patch('apps.nlp.views.converse') as provider:
            r=self.client.post(path+'turn/',{'message':'Yes, correct.'},format='json')
            provider.assert_not_called()
        self.assertEqual(r.status_code,200);self.assertEqual(r.data['status'],'confirmed')
        self.assertEqual(r.data['final_result']['request']['difficulty'],d['difficulty'])
        self.assertEqual(r.data['final_result']['booking_status'],'not_booked')

    def test_affirmation_does_not_confirm_stale_summary(self):
        from .controller import summary
        from .views import intake_context
        from .models import ConversationMessage
        path=self.start();d=self.ready_draft();s=ConversationSession.objects.get();ctx=intake_context(s.learner)
        ConversationMessage.objects.create(session=s,role='assistant',content=summary(d,ctx))
        from datetime import datetime,timedelta
        from zoneinfo import ZoneInfo
        d['preferred_date']=(datetime.now(ZoneInfo(ctx['time_zone'])).date()+timedelta(days=3)).isoformat()
        self.client.patch(path,{'action':'edit','draft':d},format='json')
        with patch('apps.nlp.views.converse',return_value=({'assistant_message':summary(d,ctx),'draft':d,'relevance':'relevant'},0,0)):
            r=self.client.post(path+'turn/',{'message':'Yes, correct'},format='json')
        self.assertEqual(r.data['status'],'active');self.assertIsNone(r.data['final_result'])

    def test_affirmation_with_correction_is_not_confirmation(self):
        from .controller import affirmative
        for text in ('Yes, correct','That’s right','Exactly','ဟုတ်ပါတယ်။','对的，没问题'):
            self.assertTrue(affirmative(text))
        for text in ('Yes, but Friday','Yes, change the time','No','Correct the date'):
            self.assertFalse(affirmative(text))

    def test_project_scope_required_and_final_routing(self):
        path=self.start(); d=self.ready_draft()
        d.update(consultation_type='technical',consultation_scope=None,difficulty='Debugging my Python project',preferred_language='Myanmar or English')
        self.assertEqual(self.client.patch(path,{'action':'confirm','draft':d},format='json').status_code,400)
        d['consultation_scope']='learner_project'
        r=self.client.patch(path,{'action':'confirm','draft':d},format='json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data['final_result']['routing'],'faculty_matching')
        self.assertEqual(r.data['final_result']['preferred_languages'],['Myanmar','English'])
        self.assertEqual(r.data['final_result']['request']['consultation_scope'],'learner_project')

    def test_contradictory_type_cannot_confirm(self):
        path=self.start();d=self.ready_draft()
        for kind,scope in [('technical','learner_project'),('other','administrative')]:
            d.update(consultation_type=kind,consultation_scope=scope,difficulty='Understanding nested loops in Python')
            self.assertEqual(self.client.patch(path,{'action':'confirm','draft':d},format='json').status_code,400)

    def test_project_without_module_routes_for_review(self):
        path=self.start();d=self.ready_draft()
        d.update(consultation_type='technical',consultation_scope='learner_project',difficulty='Debugging my Python project',module_code=None,topic_code=None,topic_resolution='no_match')
        r=self.client.patch(path,{'action':'confirm','draft':d},format='json')
        self.assertEqual(r.status_code,200);self.assertEqual(r.data['final_result']['routing'],'coordinator_review')

    def test_purpose_stability_and_language_alternatives(self):
        from .routing import stabilize_purpose, language_options, purpose_evidence
        old=dict(consultation_type='academic',consultation_scope='coursework')
        proposed=dict(consultation_type='other',consultation_scope='administrative')
        self.assertEqual(stabilize_purpose(old,proposed,'Tomorrow afternoon','preferred_date'),old)
        self.assertEqual(purpose_evidence('I need help understanding OOP in Python'),('academic','coursework'))
        self.assertEqual(purpose_evidence('My Python project keeps crashing'),('technical','learner_project'))
        self.assertEqual(purpose_evidence('Cannot access institutional LMS'),('technical','institutional_system'))
        self.assertEqual(language_options('Myanmar or English'),['Myanmar','English'])
        with self.assertRaises(ValueError): language_options('English and Myanmar')

    def test_manual_non_30_duration_cannot_override_policy(self):
        path=self.start();d=self.ready_draft();d.update(duration_preference='fixed',duration_minutes=90)
        r=self.client.patch(path,{'action':'confirm','draft':d},format='json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data['final_result']['request']['duration_minutes'],30)
        self.assertRegex(r.data['final_result']['request']['preferred_date'],r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(r.data['final_result']['request']['preferred_time'],'12:00-17:00')

    def test_ambiguous_time_requires_clarification(self):
        path=self.start();d=self.ready_draft();d['preferred_time']='2'
        r=self.client.patch(path,{'action':'confirm','draft':d},format='json')
        self.assertEqual(r.status_code,400)
        r=self.client.patch(path,{'action':'edit','draft':d},format='json')
        self.assertEqual(r.status_code,200);self.assertIn('preferred_time',r.data['missing'])

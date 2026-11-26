from copy import deepcopy
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from apps.directory.models import Qualification,AcademicModule,QualificationModule,AcademicTopic,LearnerProfile,FacultyProfile,FacultyExpertise
from apps.nlp.models import ConversationSession,ConsultationDraft
from apps.nlp.policy import FIELDS
from .policy import DEFAULT,academic_score,validate_policy
from .models import RecommendationRun

class ScoreTests(SimpleTestCase):
    def test_score_and_pending(self):
        r=academic_score({'module':1,'topic':1,'experience':.8,'qualification':1,'availability':None,'mode':None},DEFAULT)
        self.assertEqual(r['academic_points'],77);self.assertEqual(r['academic_score'],96.25);self.assertIsNone(r['final_score'])
    def test_topic_not_assessed(self):
        r=academic_score({'module':1,'topic':None,'experience':.8,'qualification':1},DEFAULT)
        self.assertEqual(r['academic_maximum'],55);self.assertEqual(r['academic_score'],94.55)
    def test_policy(self):
        p=deepcopy(DEFAULT);p['weights']['module']=29
        with self.assertRaises(ValueError):validate_policy(p)

@override_settings(DEBUG=True)
class RecommendationTests(TestCase):
    def setUp(self):
        U=get_user_model();self.user=U.objects.create_user(username='learner');self.staff=U.objects.create_user(username='staff',is_staff=True);self.owner=U.objects.create_superuser(username='admin',password='password123',email='admin@example.org')
        q=Qualification.objects.create(code='Q',name='Qualification');m=AcademicModule.objects.create(code='M',name='Module');QualificationModule.objects.create(qualification=q,module=m);t=AcademicTopic.objects.create(code='T',name='Topic',module=m)
        l=LearnerProfile.objects.create(user=self.user,learner_id='L',full_name='Learner',email='l@example.org',qualification=q);l.current_modules.add(m)
        s=ConversationSession.objects.create(owner=self.user,learner=l,status='confirmed');d={k:None for k in FIELDS};d.update(consultation_type='academic',module_code='M',topic_code='T',topic_resolution='exact',urgency='normal',difficulty='Topic',preferred_date='flexible',preferred_time='flexible',duration_preference='flexible',mode='online',preferred_language='English')
        self.draft=ConsultationDraft.objects.create(session=s,data=d,confirmed_at=timezone.now(),final_result={'schema_version':'1.1','request_id':str(s.pk),'learner_id':'L','qualification_code':'Q','request':d});self.path=f'/api/matching/requests/{s.pk}/';self.client=APIClient();self.client.force_authenticate(self.user)
        for fid,approved,exact,lang in [('F1',True,True,'English'),('F2',True,False,'English'),('F3',False,True,'English'),('F4',True,True,'Chinese')]:
            f=FacultyProfile.objects.create(faculty_id=fid,full_name=fid,email=f'{fid}@example.org',languages=[lang],consultation_modes=['Online'],teaching_experience_years=8);f.qualifications.add(q)
            e=FacultyExpertise.objects.create(faculty=f,module=m,expertise_level='Expert',verified_by='Verifier',last_reviewed=timezone.localdate(),eligible_for_consultation=approved);e.qualifications.add(q)
            if exact:e.catalogue_topics.add(t)
    def test_eligibility_and_idempotency(self):
        r=self.client.post(self.path,{},format='json');self.assertEqual(r.status_code,200);self.assertEqual([c['faculty_id'] for c in r.data['result']['candidates']],['F1']);self.assertNotIn('excluded',r.data['result']);self.assertFalse(r.data['result']['availability_checked']);self.client.post(self.path,{},format='json');self.assertEqual(RecommendationRun.objects.count(),1)
        self.client.force_authenticate(self.staff);r=self.client.get(self.path).data['result'];self.assertEqual(r['eligible_candidate_count'],2);self.assertEqual(len(r['excluded']),2);self.assertEqual(r['candidates'][0]['academic_rank'],1)
    def test_permissions(self):
        other=get_user_model().objects.create_user(username='other');self.client.force_authenticate(other);self.assertEqual(self.client.get(self.path).status_code,404)
        self.client.force_authenticate(self.user);self.assertEqual(self.client.post(self.path,{'rerun':True},format='json').status_code,403)
        self.client.force_authenticate(self.staff);self.assertEqual(self.client.post('/api/matching/policy/',DEFAULT,format='json').status_code,403)
    def test_policy_version_and_rerun(self):
        self.client.post(self.path,{},format='json');self.client.force_authenticate(self.owner);r=self.client.post('/api/matching/policy/',DEFAULT,format='json');self.assertEqual(r.status_code,201);new=self.client.post(self.path,{'rerun':True},format='json').data['result'];self.assertEqual(new['policy_version'],r.data['version']);self.assertEqual(RecommendationRun.objects.count(),2)
    def test_technical_review(self):
        final=self.draft.final_result;final['request']['consultation_type']='technical';self.draft.final_result=final;self.draft.save();r=self.client.post(self.path,{},format='json').data['result'];self.assertEqual(r['status'],'needs_review');self.assertEqual(r['candidates'],[])

    def test_legacy_snapshot_without_resolution_fields(self):
        final=deepcopy(self.draft.final_result)
        final['schema_version']='1.0'
        for field in ('topic_resolution','urgency_reason'):
            final['request'].pop(field)
        final['request']['urgency']=None
        self.draft.final_result=final;self.draft.save(update_fields=['final_result'])
        r=self.client.post(self.path,{},format='json')
        self.assertEqual(r.status_code,200)
        self.assertEqual([c['faculty_id'] for c in r.data['result']['candidates']],['F1'])
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.final_result,final)

    def test_current_snapshot_requires_urgency_and_topic_resolution(self):
        for field in ('urgency','topic_resolution'):
            with self.subTest(field=field):
                final=deepcopy(self.draft.final_result)
                original=deepcopy(final)
                final['request'][field]=None
                self.draft.final_result=final;self.draft.save(update_fields=['final_result'])
                r=self.client.post(self.path,{},format='json')
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.data['result']['status'],'needs_review')
                self.assertEqual(r.data['result']['candidates'],[])
                self.draft.recommendations.all().delete()
                self.draft.final_result=original;self.draft.save(update_fields=['final_result'])

    def test_project_technical_matches_faculty(self):
        final=deepcopy(self.draft.final_result);final['schema_version']='1.2'
        final['request'].update(consultation_type='technical',consultation_scope='learner_project',difficulty='Debugging my Python project',preferred_language='Myanmar or English')
        self.draft.final_result=final;self.draft.save(update_fields=['final_result'])
        r=self.client.post(self.path,{},format='json')
        self.assertEqual(r.status_code,200);self.assertEqual([c['faculty_id'] for c in r.data['result']['candidates']],['F1'])
        self.assertEqual(r.data['result']['status'],'academic_match_found')

    def test_institutional_technical_never_matches_faculty(self):
        final=deepcopy(self.draft.final_result);final['schema_version']='1.2'
        final['request'].update(consultation_type='technical',consultation_scope='institutional_system',difficulty='Cannot access institutional LMS')
        self.draft.final_result=final;self.draft.save(update_fields=['final_result'])
        r=self.client.post(self.path,{},format='json');self.assertEqual(r.status_code,200)
        self.assertEqual(r.data['result']['status'],'needs_review');self.assertEqual(r.data['result']['candidates'],[])

    def test_project_without_module_needs_review(self):
        final=deepcopy(self.draft.final_result);final['schema_version']='1.2'
        final['request'].update(consultation_type='technical',consultation_scope='learner_project',difficulty='Debugging my project',module_code=None,topic_code=None,topic_resolution='no_match')
        self.draft.final_result=final;self.draft.save(update_fields=['final_result'])
        r=self.client.post(self.path,{},format='json');self.assertEqual(r.status_code,200)
        self.assertEqual(r.data['result']['status'],'needs_review');self.assertEqual(r.data['result']['candidates'],[])

    def test_automatic_scheduling_and_fixed_duration(self):
        from datetime import timedelta,time
        from zoneinfo import ZoneInfo
        from apps.scheduling.models import FacultyWindow,ScheduleRun
        from apps.scheduling.slots import local_time
        l=self.draft.session.learner; z=l.time_zone
        day=(timezone.now().astimezone(ZoneInfo(z)).date()+timedelta(days=2)).isoformat()
        final=deepcopy(self.draft.final_result);final['schema_version']='1.3';final['confirmed_at']=self.draft.confirmed_at.isoformat()
        final['request'].update(preferred_date=day,preferred_time='at 14:10',duration_preference='fixed',duration_minutes=30,consultation_scope='coursework')
        self.draft.final_result=final;self.draft.save(update_fields=['final_result'])
        f=FacultyProfile.objects.get(faculty_id='F1');f.time_zone=z;f.working_days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];f.working_hours_start=time(9);f.working_hours_end=time(17);f.save()
        FacultyWindow.objects.create(faculty=f,start=local_time(day+'T13:00',z),end=local_time(day+'T16:00',z),kind='available',mode='online',created_by=self.staff)
        path=self.path.replace('/matching/','/scheduling/')
        r=self.client.post(path,{'duration_minutes':120,'windows':[]},format='json');self.assertEqual(r.status_code,201)
        result=r.data['result'];self.assertEqual(result['duration_minutes'],30);self.assertEqual(result['status'],'slots_found')
        candidate=result['candidates'][0];self.assertEqual(candidate['faculty_id'],'F1');slot=candidate['slots'][0]
        self.assertEqual(slot['start'],local_time(day+'T14:10',z).isoformat());self.assertEqual(slot['end'],local_time(day+'T14:40',z).isoformat())
        self.assertEqual(self.client.post(path,{},format='json').status_code,200);self.assertEqual(ScheduleRun.objects.count(),1)
        self.assertEqual(self.client.patch(path,{'run_id':result['run_id'],'faculty_id':'F1',**slot},format='json').status_code,200)
        self.draft.refresh_from_db();self.assertEqual(self.draft.final_result,final)

    def test_automatic_alternatives_require_explicit_acceptance(self):
        from datetime import timedelta,time
        from zoneinfo import ZoneInfo
        from apps.scheduling.models import FacultyWindow
        from apps.scheduling.slots import local_time
        z=self.draft.session.learner.time_zone; today=timezone.now().astimezone(ZoneInfo(z)).date()
        preferred=(today+timedelta(days=2)).isoformat(); other=(today+timedelta(days=3)).isoformat()
        final=deepcopy(self.draft.final_result);final['schema_version']='1.3';final['confirmed_at']=self.draft.confirmed_at.isoformat()
        final['request'].update(preferred_date=preferred,preferred_time='afternoon',duration_preference='fixed',duration_minutes=30,consultation_scope='coursework')
        self.draft.final_result=final;self.draft.save(update_fields=['final_result'])
        f=FacultyProfile.objects.get(faculty_id='F1');f.time_zone=z;f.working_days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];f.working_hours_start=time(9);f.working_hours_end=time(17);f.save()
        FacultyWindow.objects.create(faculty=f,start=local_time(other+'T13:00',z),end=local_time(other+'T16:00',z),kind='available',mode='online',created_by=self.staff)
        path=self.path.replace('/matching/','/scheduling/')
        r=self.client.post(path,{},format='json');self.assertEqual(r.status_code,201);result=r.data['result'];self.assertTrue(result['alternative_offer'])
        slot=result['candidates'][0]['slots'][0];body={'run_id':result['run_id'],'faculty_id':'F1',**slot}
        self.assertEqual(self.client.patch(path,body,format='json').status_code,400)
        self.assertEqual(self.client.patch(path,{**body,'accept_alternative':True},format='json').status_code,200)

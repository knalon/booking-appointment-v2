from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.directory.models import Qualification, FacultyProfile
from apps.matching import tests as matching_tests
from apps.scheduling.models import Appointment, Notification, ScheduleRun
from .models import CoordinatorProfile, ReviewCase, ReviewEvent
from .services import sync_case


@override_settings(DEBUG=True)
class CoordinatorTests(TestCase):
    def setUp(self):
        matching_tests.RecommendationTests.setUp(self)
        self.q=Qualification.objects.get(code='Q');self.other_q=Qualification.objects.create(code='Q2',name='Other qualification')
        self.coordinator=self.make_user('coordinator_q',self.q)
        self.other=self.make_user('coordinator_q2',self.other_q)
        self.manager=self.make_user('programme_manager',self.q,'programme_manager')
        self.base='/api/coordinator/';self.notifications='/api/scheduling/notifications/'

    def make_user(self,name,q,role='coordinator'):
        u=get_user_model().objects.create_user(username=name,password='DemoPass!923')
        p=CoordinatorProfile.objects.create(user=u,full_name=name,role=role);p.qualifications.add(q);return u

    def login_as(self,user): self.client.force_authenticate(user)
    def action(self,case,action,**extra): return self.client.post(f'{self.base}cases/{case.pk}/',{'action':action,**extra},format='json')
    def request_review(self):
        self.login_as(self.user);r=self.client.post(self.base+'learner-cases/',{'request_id':str(self.draft.session_id)},format='json');self.assertEqual(r.status_code,200,r.content);return ReviewCase.objects.get(pk=r.data['id'])

    def test_coordinator_login_and_not_management(self):
        client=APIClient();r=client.post(self.base+'login/',{'username':self.coordinator.username,'password':'DemoPass!923'},format='json');self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(client.get(self.base+'session/').data['qualifications'],['Q']);self.assertEqual(client.get('/api/directory/session/').status_code,403)
        self.assertEqual(client.get(self.path).status_code,404)

    def test_scope_and_cross_qualification_access(self):
        c=self.request_review();self.login_as(self.other)
        self.assertEqual(self.client.get(self.base+'cases/').data['cases'],[])
        self.assertEqual(self.client.get(f'{self.base}cases/{c.pk}/').status_code,404)
        self.assertEqual(self.action(c,'claim').status_code,404)
        self.login_as(self.coordinator);self.assertEqual(self.client.get(f'{self.base}cases/{c.pk}/').status_code,200)

    def test_urgent_case_created_once_and_notified(self):
        final=self.draft.final_result;final['request']['urgency']='urgent';self.draft.final_result=final;self.draft.save()
        c=sync_case(self.draft.pk);sync_case(self.draft.pk);self.assertTrue(c.urgent);self.assertEqual(c.reason,'urgent');self.assertEqual(ReviewCase.objects.count(),1)
        self.assertEqual(Notification.objects.filter(review_case=c,recipient=self.coordinator).count(),1);self.assertFalse(Notification.objects.filter(review_case=c,recipient=self.other).exists())

    def test_no_slots_detected_and_backfilled(self):
        ScheduleRun.objects.create(draft=self.draft,result={'status':'no_slots'})
        self.login_as(self.coordinator);r=self.client.post(self.base+'cases/',{},format='json');self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(ReviewCase.objects.get(draft=self.draft).reason,'no_slots')

    def test_claim_prevents_other_coordinator_actions(self):
        c=self.request_review();self.login_as(self.coordinator);self.assertEqual(self.action(c,'claim').status_code,200)
        second=self.make_user('second',self.q);self.login_as(second);self.assertEqual(self.action(c,'claim').status_code,400);self.assertEqual(self.action(c,'message',note='test').status_code,403)

    def test_public_messages_and_private_notes(self):
        c=self.request_review();self.login_as(self.coordinator);self.action(c,'claim')
        self.assertEqual(self.action(c,'note',note='Internal information').status_code,200);self.assertEqual(self.action(c,'message',note='Please refresh your availability.').status_code,200)
        self.login_as(self.user);r=self.client.get(self.base+'learner-cases/');details=[e['detail'] for e in r.data[0]['events']];self.assertIn('Please refresh your availability.',details);self.assertNotIn('Internal information',details)
        self.assertEqual(self.client.get(self.notifications).data['unread'],1);n=self.client.get(self.notifications).data['items'][0];self.assertEqual(n['review_case_id'],c.pk);self.assertIsNone(n['appointment_id']);self.assertEqual(self.client.post(self.notifications,{'id':n['id']},format='json').data['unread'],0)

    def test_suggestions_cannot_bypass_eligibility(self):
        c=self.request_review();self.login_as(self.coordinator);self.action(c,'claim')
        self.assertEqual(self.action(c,'suggest',faculty_id='F3').status_code,400)
        self.assertEqual(self.action(c,'suggest',faculty_id='F1').status_code,200)
        self.assertFalse(Appointment.objects.exists());self.assertTrue(ReviewEvent.objects.filter(case=c,action='suggest',learner_visible=True).exists())

    def test_escalation_and_manager_resolution(self):
        c=self.request_review();self.login_as(self.coordinator);self.action(c,'claim');self.assertEqual(self.action(c,'escalate',note='Needs further review').status_code,200)
        self.assertEqual(self.action(c,'resolve',note='Should not work').status_code,403)
        self.login_as(self.manager);self.assertTrue(Notification.objects.filter(review_case=c,recipient=self.manager).exists());self.assertEqual(self.action(c,'resolve',note='Please contact the support desk.').status_code,200)
        c.refresh_from_db();self.assertEqual(c.status,'resolved')

    def test_resolved_case_not_reopened_without_new_signal(self):
        c=self.request_review();self.login_as(self.coordinator);self.action(c,'claim');self.action(c,'resolve',note='Answered');sync_case(self.draft.pk)
        c.refresh_from_db();self.assertEqual(c.status,'resolved');self.request_review();c.refresh_from_db();self.assertEqual(c.status,'open');self.assertEqual(ReviewCase.objects.count(),1)

    def test_archived_account_and_notifications_scope_revoked(self):
        c=self.request_review();self.login_as(self.coordinator);self.assertEqual(self.client.get(self.notifications).data['unread'],1)
        p=self.coordinator.coordinator_profile;p.active=False;p.save();self.assertEqual(self.client.get(self.base+'session/').status_code,403);self.assertEqual(self.client.get(self.base+'cases/').status_code,403);self.assertEqual(self.client.get(self.notifications).data['unread'],0)

    def test_appointment_oversight_read_only_and_scoped(self):
        f=FacultyProfile.objects.get(faculty_id='F1');start=timezone.now()+timedelta(days=1)
        a=Appointment.objects.create(draft=self.draft,faculty=f,start=start,end=start+timedelta(minutes=30),mode='online',status='confirmed')
        self.login_as(self.coordinator);r=self.client.get(self.base+'appointments/');self.assertEqual([x['id'] for x in r.data],[a.pk]);self.assertEqual(self.client.post(self.base+'appointments/',{},format='json').status_code,405)
        self.assertEqual(self.client.post(f'/api/scheduling/appointments/{a.pk}/action/',{'action':'cancel'},format='json').status_code,404)
        self.login_as(self.other);self.assertEqual(self.client.get(self.base+'appointments/').data,[])

    def test_only_superuser_can_create_accounts(self):
        body={'username':'new_coordinator','password':'StrongExample!92','full_name':'New Coordinator','role':'coordinator','qualifications':['Q'],'active':True}
        self.login_as(self.staff);self.assertEqual(self.client.post(self.base+'accounts/',body,format='json').status_code,403)
        self.login_as(self.owner);r=self.client.post(self.base+'accounts/',body,format='json');self.assertEqual(r.status_code,201,r.data)
        p=CoordinatorProfile.objects.get(pk=r.data['id']);self.assertFalse(p.user.is_staff);self.assertFalse(p.user.is_superuser);self.assertEqual(list(p.qualifications.values_list('code',flat=True)),['Q'])

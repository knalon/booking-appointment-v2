from datetime import timedelta,time
from zoneinfo import ZoneInfo
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.matching import tests as matching_tests
from apps.directory.models import FacultyProfile,LearnerProfile
from apps.nlp.models import ConversationSession,ConsultationDraft
from .models import Appointment,AppointmentEvent,Notification,FacultyWindow,SlotSelection,ScheduleRun
from .slots import local_time
from .booking import conflicts

@override_settings(DEBUG=True)
class BookingTests(TestCase):
    def setUp(self):
        matching_tests.RecommendationTests.setUp(self)
        self.faculty=FacultyProfile.objects.get(faculty_id='F1');self.faculty_user=get_user_model().objects.create_user(username='faculty');self.faculty.user=self.faculty_user
        z=self.draft.session.learner.time_zone;self.zone=z
        self.day=(timezone.now().astimezone(ZoneInfo(z)).date()+timedelta(days=2)).isoformat()
        self.faculty.time_zone=z;self.faculty.working_days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];self.faculty.working_hours_start=time(9);self.faculty.working_hours_end=time(17);self.faculty.save()
        self.window=FacultyWindow.objects.create(faculty=self.faculty,start=local_time(self.day+'T13:00',z),end=local_time(self.day+'T16:00',z),kind='available',mode='online',created_by=self.staff)
        final=self.draft.final_result;final['schema_version']='1.3';final['confirmed_at']=self.draft.confirmed_at.isoformat();final['request'].update(preferred_date=self.day,preferred_time='afternoon',duration_preference='fixed',duration_minutes=30,consultation_scope='coursework');self.draft.final_result=final;self.draft.save()
        self.schedule=self.path.replace('/matching/','/scheduling/');self.base='/api/scheduling/appointments/';self.notifications='/api/scheduling/notifications/'
        r=self.client.post(self.schedule,{},format='json');self.assertEqual(r.status_code,201,r.data);result=r.data['result'];slot=result['candidates'][0]['slots'][0]
        r=self.client.patch(self.schedule,{'run_id':result['run_id'],'faculty_id':'F1',**slot},format='json');self.assertEqual(r.status_code,200,r.data)
        self.body={'request_id':str(self.draft.session_id),'selection':r.data['selection']}
    def submit(self):
        r=self.client.post(self.base,self.body,format='json');self.assertEqual(r.status_code,201,r.data);return r.data['id']
    def action(self,pk,action,**extra): return self.client.post(f'{self.base}{pk}/action/',{'action':action,**extra},format='json')
    def test_submit_and_approval(self):
        pk=self.submit();self.assertEqual(self.client.post(self.base,self.body,format='json').status_code,200);self.assertEqual(Appointment.objects.count(),1)
        self.assertEqual(self.action(pk,'accept').status_code,400)
        self.client.force_authenticate(self.faculty_user);self.assertEqual(self.client.get(self.notifications).data['unread'],1)
        r=self.action(pk,'accept');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['status'],'confirmed');self.assertEqual(AppointmentEvent.objects.count(),2)
        self.client.force_authenticate(self.user);self.assertEqual(self.client.get(self.notifications).data['unread'],2)
    def test_overlap_and_release(self):
        pk=self.submit();a=Appointment.objects.get(pk=pk);self.assertTrue(conflicts(a.start+timedelta(minutes=15),a.end+timedelta(minutes=15),faculty=self.faculty.pk).exists());self.assertFalse(conflicts(a.end,a.end+timedelta(minutes=30),faculty=self.faculty.pk).exists())
        self.assertTrue(conflicts(a.start,a.end,learner=self.draft.session.learner_id).exists())
        self.assertEqual(self.action(pk,'cancel').status_code,200);self.assertFalse(conflicts(a.start,a.end,faculty=self.faculty.pk).exists())
    def test_private_notifications_and_actions(self):
        pk=self.submit();n=Notification.objects.get(recipient=self.faculty_user);self.assertEqual(self.client.post(self.notifications,{'id':n.pk},format='json').status_code,404)
        other=get_user_model().objects.create_user(username='outsider');self.client.force_authenticate(other);self.assertEqual(self.client.get(self.base).data,[]);self.assertEqual(self.action(pk,'cancel').status_code,404)
        self.client.force_authenticate(self.faculty_user);self.assertEqual(self.client.post(self.notifications,{'id':n.pk},format='json').data['unread'],0)
    def test_reschedule_and_learner_approval(self):
        pk=self.submit();a=Appointment.objects.get(pk=pk);old=a.start
        self.client.force_authenticate(self.faculty_user);r=self.action(pk,'propose',start=self.day+'T15:00');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['status'],'reschedule_requested');self.assertFalse(conflicts(old,old+timedelta(minutes=30),faculty=self.faculty.pk).exists())
        self.client.force_authenticate(self.user);r=self.action(pk,'accept');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['status'],'confirmed')
    def test_expiration_releases_and_notifies(self):
        pk=self.submit();Appointment.objects.filter(pk=pk).update(expires_at=timezone.now()-timedelta(seconds=1));a=Appointment.objects.get(pk=pk)
        self.assertFalse(conflicts(a.start,a.end,faculty=self.faculty.pk).exists());self.assertEqual(self.client.get(self.base).data[0]['status'],'expired');self.assertEqual(AppointmentEvent.objects.filter(action='expired').count(),1)
    def test_window_changes_blocked_while_held(self):
        self.submit();self.client.force_authenticate(self.faculty_user);r=self.client.patch('/api/scheduling/availability/',{'id':self.window.pk,'active':False},format='json');self.assertEqual(r.status_code,400)
    def test_stale_selection_rejected(self):
        self.body['selection']['start']='2020-01-01T00:00:00+00:00';self.assertEqual(self.client.post(self.base,self.body,format='json').status_code,400);self.assertFalse(Appointment.objects.exists())
    def test_second_learner_cannot_submit_overlap(self):
        self.submit();s=SlotSelection.objects.get(draft=self.draft);old=self.draft.session.learner
        u=get_user_model().objects.create_user(username='learner2');l=LearnerProfile.objects.create(user=u,learner_id='L2',full_name='Learner 2',email='l2@example.org',qualification=old.qualification,time_zone=old.time_zone);l.current_modules.set(old.current_modules.all());session=ConversationSession.objects.create(owner=u,learner=l,status='confirmed')
        from copy import deepcopy
        final=deepcopy(self.draft.final_result);final.update(learner_id='L2',request_id=str(session.pk));d=ConsultationDraft.objects.create(session=session,final_result=final,confirmed_at=timezone.now());run=ScheduleRun.objects.create(draft=d,result=s.run.result);SlotSelection.objects.create(draft=d,run=run,faculty=s.faculty,start=s.start+timedelta(minutes=15),end=s.end+timedelta(minutes=15),mode=s.mode)
        self.client.force_authenticate(u);selection={**self.body['selection'],'run_id':run.pk,'start':(s.start+timedelta(minutes=15)).isoformat(),'end':(s.end+timedelta(minutes=15)).isoformat()};r=self.client.post(self.base,{'request_id':str(session.pk),'selection':selection},format='json');self.assertEqual(r.status_code,400);self.assertEqual(Appointment.objects.count(),1)

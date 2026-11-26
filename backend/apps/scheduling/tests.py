from datetime import datetime,timezone,timedelta
from django.test import SimpleTestCase
from .slots import local_time,overlaps,slot_starts,operational_score
from apps.matching.policy import DEFAULT

class SlotTests(SimpleTestCase):
    def test_time_zone(self):
        self.assertEqual(local_time('2026-12-01T09:00','Asia/Yangon'),datetime(2026,12,1,2,30,tzinfo=timezone.utc))
    def test_slots(self):
        a=local_time('2026-12-01T09:01','Asia/Yangon');b=a+timedelta(hours=1)
        slots=list(slot_starts(a,b,30));self.assertEqual(len(slots),2);self.assertTrue(all(x>=a and y<=b for x,y in slots))
    def test_overlap(self):
        a=datetime(2026,12,1,tzinfo=timezone.utc);b=a+timedelta(minutes=30);c=b+timedelta(minutes=30)
        self.assertFalse(overlaps(a,b,b,c));self.assertTrue(overlaps(a,c,b,c))
    def test_complete_score(self):
        r=operational_score(dict(module=.85,topic=.5,experience=.2,qualification=1,availability=1,mode=1),DEFAULT)
        self.assertEqual(r['final_score'],71);self.assertEqual(r['contributions']['mode'],5)
    def test_missing_topic(self):
        r=operational_score(dict(module=1,topic=None,experience=1,qualification=1,availability=1,mode=1),DEFAULT)
        self.assertEqual(r['maximum'],75);self.assertEqual(r['final_score'],100)

from datetime import time
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone as dj_timezone
from rest_framework.test import APIClient
from apps.directory.models import FacultyProfile
from .models import FacultyWindow
from io import StringIO

class FacultyWorkspaceTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.user=User.objects.create_user(username='faculty_test',password='testpass123')
        self.other=User.objects.create_user(username='other',password='testpass123')
        self.f=FacultyProfile.objects.create(user=self.user,faculty_id='FTEST',full_name='Test Faculty',email='ftest@example.invalid',time_zone='Asia/Yangon',working_days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],working_hours_start=time(9),working_hours_end=time(17),consultation_modes=['Online'])
        self.g=FacultyProfile.objects.create(user=self.other,faculty_id='FOTHER',full_name='Other Faculty',email='other@example.invalid')
        self.client=APIClient();self.client.force_authenticate(self.user)
        self.path='/api/scheduling/availability/'
        day=(dj_timezone.now()+timedelta(days=2)).date().isoformat()
        self.data={'faculty_id':self.f.faculty_id,'start':day+'T10:00','end':day+'T11:00','kind':'available','mode':'online'}
    def test_own_calendar_only(self):
        r=self.client.get(self.path);self.assertEqual(r.status_code,200);self.assertEqual([f['faculty_id'] for f in r.data['faculty']],[self.f.faculty_id])
        self.assertEqual(self.client.get(self.path,{'faculty':self.g.faculty_id}).status_code,403)
    def test_cross_faculty_write_denied(self):
        r=self.client.post(self.path,{**self.data,'faculty_id':self.g.faculty_id},format='json');self.assertEqual(r.status_code,404)
        a=dj_timezone.now()+timedelta(days=2);w=FacultyWindow.objects.create(faculty=self.g,start=a,end=a+timedelta(hours=1),kind='busy',created_by=self.other)
        self.assertEqual(self.client.patch(self.path,{'id':w.pk,'active':False},format='json').status_code,404);w.refresh_from_db();self.assertTrue(w.active)
    def test_repeat_edit_archive_restore(self):
        r=self.client.post(self.path,{**self.data,'repeat_weeks':2},format='json');self.assertEqual(r.status_code,201);self.assertEqual(FacultyWindow.objects.filter(faculty=self.f).count(),2)
        w=FacultyWindow.objects.filter(faculty=self.f).first();self.assertEqual(self.client.patch(self.path,{'id':w.pk,'end':self.data['start'][:10]+'T12:00'},format='json').status_code,200)
        for active in (False,True):
            self.assertEqual(self.client.patch(self.path,{'id':w.pk,'active':active},format='json').status_code,200);w.refresh_from_db();self.assertEqual(w.active,active)
    def test_invalid_hours_and_mode(self):
        self.assertEqual(self.client.post(self.path,{**self.data,'mode':'facetoface'},format='json').status_code,400)
        self.assertEqual(self.client.post(self.path,{**self.data,'end':self.data['start'][:10]+'T19:00'},format='json').status_code,400)
        self.assertFalse(FacultyWindow.objects.exists())
    def test_session_and_inactive_profile(self):
        path='/api/scheduling/faculty/session/'
        self.assertEqual(self.client.get(path).data['faculty_id'],self.f.faculty_id)
        self.f.status='Inactive';self.f.save();self.assertEqual(self.client.get(path).status_code,403);self.assertEqual(self.client.get(self.path).status_code,403)
    def test_unlinked_user_denied(self):
        user=get_user_model().objects.create_user(username='unlinked');self.client.force_authenticate(user)
        self.assertEqual(self.client.get(self.path).status_code,403)
        self.assertEqual(self.client.get('/api/scheduling/faculty/session/').status_code,403)
    @override_settings(DEBUG=True)
    def test_demo_provision_idempotent(self):
        p=FacultyProfile.objects.create(faculty_id='FNEW',full_name='Demo',email='new@example.invalid')
        call_command('provision_demo_faculty',confirm='DEMO-ONLY',stdout=StringIO());p.refresh_from_db();uid=p.user_id;password=p.user.password
        self.assertTrue(p.user.check_password('1234'));self.assertFalse(p.user.is_staff)
        call_command('provision_demo_faculty',confirm='DEMO-ONLY',stdout=StringIO());p.refresh_from_db();self.assertEqual(p.user_id,uid);self.assertEqual(p.user.password,password)
    @override_settings(DEBUG=False)
    def test_demo_provision_blocked_in_production(self):
        with self.assertRaises(CommandError): call_command('provision_demo_faculty',confirm='DEMO-ONLY',stdout=StringIO())

class AutomaticPreferenceTests(SimpleTestCase):
    def setUp(self):
        from .preferences import search_preferences
        self.search=search_preferences
        self.now=datetime(2026,11,26,18,0,tzinfo=timezone.utc) # Nov 27 in Yangon
        self.final={'confirmed_at':self.now.isoformat(),'request':{'preferred_date':'tomorrow','preferred_time':'afternoon'}}
    def test_relative_date_anchored_to_confirmation(self):
        data=self.search(self.final,'Asia/Yangon',self.now+timedelta(days=1))
        self.assertEqual(data['windows'],[{'start':'2026-11-28T12:00','end':'2026-11-28T17:00','kind':'preferred'}])
        self.assertEqual(data['duration_minutes'],30)
    def test_exact_and_after_time(self):
        self.final['request']['preferred_time']='2:10 PM'
        self.assertEqual(self.search(self.final,'Asia/Yangon',self.now)['windows'][0]['end'],'2026-11-28T14:40')
        self.final['request']['preferred_time']='after 1 PM'
        self.assertEqual(self.search(self.final,'Asia/Yangon',self.now)['windows'][0]['start'],'2026-11-28T13:00')
    def test_flexible_and_alternatives(self):
        self.final['request'].update(preferred_date='flexible',preferred_time='morning')
        self.assertEqual(len(self.search(self.final,'Asia/Yangon',self.now)['windows']),30)
        alt=self.search(self.final,'Asia/Yangon',self.now,alternative=True)
        self.assertTrue(alt['alternative_offer']);self.assertTrue(all(w['kind']=='alternative' for w in alt['windows']))
    def test_ambiguous_time_not_guessed(self):
        self.final['request']['preferred_time']='2'
        with self.assertRaises(ValueError): self.search(self.final,'Asia/Yangon',self.now)
    def test_old_requested_day_does_not_move(self):
        self.assertEqual(self.search(self.final,'Asia/Yangon',self.now+timedelta(days=3))['windows'],[])

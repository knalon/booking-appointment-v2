from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import FacultyProfile, AcademicModule, AcademicTopic, Qualification, QualificationModule

class ExpertiseAPITest(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.staff=get_user_model().objects.create_user(username='staff',password='test',is_staff=True)
        self.faculty=FacultyProfile.objects.create(faculty_id='FTEST',full_name='Test',email='test@example.invalid')
        self.a=AcademicModule.objects.create(code='A',name='A')
        self.b=AcademicModule.objects.create(code='B',name='B')
        AcademicTopic.objects.create(code='A1',name='A topic',module=self.a)
        AcademicTopic.objects.create(code='B1',name='B topic',module=self.b)
        q=Qualification.objects.create(code='Q',name='Test qualification')
        self.faculty.qualifications.add(q)
        QualificationModule.objects.create(qualification=q,module=self.a,sequence=1)
        self.url='/api/directory/faculty/FTEST/expertise/'
        self.payload=dict(module='A',catalogue_topics=['A1'],qualifications=['Q'],expertise_level='Advanced',verified_by='Lead',last_reviewed='2026-01-01',eligible_for_consultation=True)
    def test_access(self):
        self.assertEqual(self.client.get('/api/directory/session/').status_code,403)
    def test_create_and_reject_mismatch(self):
        self.client.force_authenticate(self.staff)
        bad={**self.payload,'catalogue_topics':['B1']}
        self.assertEqual(self.client.post(self.url,bad,format='json').status_code,400)
        response=self.client.post(self.url,self.payload,format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(self.client.patch(self.url+str(response.data['id'])+'/',{'catalogue_topics':['B1']},format='json').status_code,400)
        self.assertEqual(self.client.post(self.url,self.payload,format='json').status_code,400)
        self.assertEqual(self.client.get('/api/directory/integrity/').data['issues'],[])
    def test_profile_edit(self):
        self.client.force_authenticate(self.staff)
        url='/api/directory/faculty/FTEST/'
        response=self.client.patch(url,{'full_name':'Updated Test','languages':['English','Myanmar']},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.faculty.refresh_from_db()
        self.assertEqual(self.faculty.full_name,'Updated Test')
        self.assertEqual(self.client.patch(url,{'languages':['Myanmar']},format='json').status_code,400)
        self.assertEqual(self.client.post(self.url,self.payload,format='json').status_code,201)
        preview=self.client.patch(url,{'qualifications':[]},format='json')
        self.assertEqual(preview.status_code,409)
        self.assertTrue(self.faculty.expertise_mappings.get().eligible_for_consultation)
        done=self.client.patch(url,{'qualifications':[],'impact_token':preview.data['impact_token']},format='json')
        self.assertEqual(done.status_code,200,done.data)
        e=self.faculty.expertise_mappings.get();self.assertFalse(e.eligible_for_consultation);self.assertEqual(e.catalogue_topics.count(),1);self.assertEqual(e.verified_by,'Lead')
    def test_edit_existing_expertise(self):
        self.client.force_authenticate(self.staff)
        response=self.client.post(self.url,self.payload,format='json')
        self.assertEqual(response.status_code,201,response.data)
        result=self.client.patch(self.url+str(response.data['id'])+'/',{'expertise_level':'Expert'},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['expertise_level'],'Expert')

    def test_teaching_assignments_follow_active_curriculum(self):
        self.client.force_authenticate(self.staff)
        url='/api/directory/faculty/FTEST/'
        self.assertEqual(self.client.patch(url,{'modules_taught':['B']},format='json').status_code,400)
        self.assertEqual(self.client.patch(url,{'modules_taught':['A']},format='json').status_code,200)
        self.assertEqual(self.client.patch(url,{'qualifications':[]},format='json').status_code,400)
        self.assertEqual(list(self.faculty.modules_taught.values_list('code',flat=True)),['A'])
        QualificationModule.objects.filter(module=self.a).update(is_active=False)
        self.assertEqual(self.client.patch(url,{'modules_taught':['A']},format='json').status_code,400)
        preview=self.client.patch(url,{'modules_taught':[]},format='json')
        self.assertEqual(preview.status_code,409)
        self.assertEqual(self.client.patch(url,{'modules_taught':[],'impact_token':preview.data['impact_token']},format='json').status_code,200)

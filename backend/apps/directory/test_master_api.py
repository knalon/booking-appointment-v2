from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Qualification, AcademicModule, QualificationModule

class ReactMasterTest(TestCase):
    def setUp(self):
        self.client=APIClient(); self.user=get_user_model().objects.create_user(username='manager',password='test',is_staff=True)
    def test_access_and_qualification_crud(self):
        url='/api/directory/master/qualifications/'
        row={'Qualification_Code':'Q','Qualification_Name':'Diploma','Status':'Active'}
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(url,{'row':row},format='json').status_code,200)
        self.assertEqual(self.client.post(url,{'row':row},format='json').status_code,409)
        self.assertEqual(self.client.post(url,{'row':{**row,'Status':'Inactive'},'original':row},format='json').status_code,200)
        self.assertFalse(Qualification.objects.get(code='Q').is_active)
        self.assertEqual(self.client.post(url,{'row':row,'original':row},format='json').status_code,409)
    def test_curriculum_and_learner_validation(self):
        self.client.force_authenticate(self.user)
        q=Qualification.objects.create(code='Q',name='Diploma'); m=AcademicModule.objects.create(code='M',name='Module')
        row={'Qualification_Code':'Q','Module_Code':'M','Sequence':'1','Status':'Active'}
        self.assertEqual(self.client.post('/api/directory/master/curriculum/',{'row':row},format='json').status_code,200)
        self.assertEqual(QualificationModule.objects.count(),1)
        learner={'Learner_ID':'L','Full_Name':'Example','Email':'l@example.invalid','Qualification':'Q','Current_Module_Code':'M','Current_Module_Codes':'M','Time_Zone':'Asia/Singapore','Preferred_Consultation_Mode':'Online','Preferred_Language':'Myanmar','Status':'Active'}
        self.assertEqual(self.client.post('/api/directory/master/learners/',{'row':learner},format='json').status_code,400)
        learner['Preferred_Language']='English; Myanmar'
        self.assertEqual(self.client.post('/api/directory/master/learners/',{'row':learner},format='json').status_code,200)

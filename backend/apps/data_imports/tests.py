from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import ImportBatch
from .services import parse_and_validate_csv, plan, confirm_import_batch, save_row
from apps.directory.models import Qualification, AcademicModule

class CatalogueImportTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='testadmin',is_staff=True)
    def preview(self,dataset,content):
        records,errors=parse_and_validate_csv(SimpleUploadedFile('data.csv',content.encode()),dataset)
        self.assertEqual(errors,[])
        counts,digest=plan(dataset,records)
        return ImportBatch.objects.create(dataset=dataset,source_filename='data.csv',records=records,preview_digest=digest,created_by=self.user,expires_at=timezone.now()+timedelta(hours=1))
    def test_create_then_unchanged(self):
        content='Qualification_Code,Qualification_Name,Status\nDIT,Diploma in IT,Active\n'
        self.assertEqual(confirm_import_batch(self.preview('qualifications',content),self.user),(1,0,0))
        self.assertEqual(confirm_import_batch(self.preview('qualifications',content),self.user),(0,0,1))
        self.assertEqual(Qualification.objects.count(),1)
    def test_stale_preview(self):
        b=self.preview('qualifications','Qualification_Code,Qualification_Name,Status\nDIT,Diploma in IT,Active\n')
        Qualification.objects.create(code='DIT',name='Another name')
        with self.assertRaises(ValueError): confirm_import_batch(b,self.user)
    def test_unknown_qualification(self):
        _,errors=parse_and_validate_csv(SimpleUploadedFile('data.csv',b'Qualification_Code,Module_Code,Sequence,Status\nDIT,PY101,1,Active\n'),'curriculum')
        self.assertTrue(errors)
    def test_module_link(self):
        Qualification.objects.create(code='DIT',name='Diploma in IT')
        AcademicModule.objects.create(code='PY101',name='Python')
        b=self.preview('curriculum','Qualification_Code,Module_Code,Sequence,Status\nDIT,PY101,1,Active\n')
        confirm_import_batch(b,self.user)
        self.assertTrue(AcademicModule.objects.get(code='PY101').qualifications.filter(code='DIT').exists())


class TopicImportTests(CatalogueImportTests):
    def test_topic_roundtrip(self):
        from apps.directory.models import AcademicTopic
        AcademicModule.objects.create(code='PY101',name='Python')
        content='Topic_Code,Module_Code,Topic_Name,Status\nPY101-T001,PY101,Functions,Active\n'
        self.assertEqual(confirm_import_batch(self.preview('topics',content),self.user),(1,0,0))
        self.assertEqual(confirm_import_batch(self.preview('topics',content),self.user),(0,0,1))
        self.assertEqual(AcademicTopic.objects.get(code='PY101-T001').name,'Functions')
    def test_topic_wrong_module(self):
        from apps.directory.models import AcademicTopic
        a=AcademicModule.objects.create(code='PY101',name='Python')
        AcademicModule.objects.create(code='DB201',name='Database')
        AcademicTopic.objects.create(code='T001',module=a,name='Functions')
        _,errors=parse_and_validate_csv(SimpleUploadedFile('data.csv',b'Topic_Code,Module_Code,Topic_Name,Status\nT001,DB201,Functions,Active\n'),'topics')
        self.assertTrue(errors)

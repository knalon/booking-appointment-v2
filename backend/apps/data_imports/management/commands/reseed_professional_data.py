from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from django.db import transaction
from apps.directory.models import Qualification, AcademicModule, QualificationModule, AcademicTopic, FacultyProfile, FacultyExpertise, LearnerProfile
from apps.data_imports.models import ImportBatch
from apps.data_imports.services import parse_and_validate_csv, save_row

FILES=[('qualifications','qualifications_v1.csv'),('modules','modules_v2.csv'),('curriculum','curriculum_v2.csv'),('topics','topics_v2.csv'),('faculty','faculty_v8.csv'),('learners','learners_v7.csv')]

class Command(BaseCommand):
    help='Replace fabricated master data only. Development databases only. Back up first.'
    def add_arguments(self,parser):
        parser.add_argument('--confirm',default='')
        parser.add_argument('--data-dir',default=str(Path(settings.BASE_DIR).parent/'data'))
    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEBUG or options['confirm']!='REPLACE-FICTIONAL-DATA':
            raise CommandError('Requires DEBUG=True and --confirm REPLACE-FICTIONAL-DATA. Back up first.')
        root=Path(options['data_dir'])
        for _,name in FILES:
            if not (root/name).is_file(): raise CommandError(f'Missing file: {root/name}')
        if FacultyProfile.objects.exclude(user=None).exists() or LearnerProfile.objects.exclude(user=None).exists():
            raise CommandError('Linked user profiles exist. This reseed refuses to remove them; reconcile manually.')
        for model in (FacultyExpertise,LearnerProfile,FacultyProfile,AcademicTopic,QualificationModule,AcademicModule,Qualification):
            model.objects.all().delete()
        for dataset,name in FILES:
            with (root/name).open('rb') as stream:
                rows,errors=parse_and_validate_csv(File(stream,name=name),dataset)
            if errors: raise CommandError(f'{name}: {errors[:5]}')
            for row in rows: save_row(dataset,row)
            self.stdout.write(f'{dataset}: {len(rows)} rows loaded (pending commit)')
        ImportBatch.objects.filter(state__in=['previewed','invalid']).update(state='expired',records=[])
        self.stdout.write(self.style.SUCCESS('Reseed validated. Master data replaced; authentication users and import history retained.'))

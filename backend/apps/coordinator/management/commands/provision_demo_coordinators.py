from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.directory.models import Qualification
from apps.coordinator.models import CoordinatorProfile

class Command(BaseCommand):
    help='Create fictional local coordinator accounts for active qualifications and one Programme Manager.'
    def add_arguments(self,parser): parser.add_argument('--confirm',required=True)
    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEBUG or options['confirm']!='DEMO-ONLY': raise CommandError('Requires DEBUG=True and --confirm DEMO-ONLY.')
        U=get_user_model(); qs=list(Qualification.objects.filter(is_active=True).order_by('code'))
        if not qs: raise CommandError('Seed qualifications first.')
        for name,username,role,qualifications in [(f'Demo Coordinator — {q.code}',f'coordinator_{q.code.lower()}','coordinator',[q]) for q in qs]+[('Demo Programme Manager','programme_manager_demo','programme_manager',qs)]:
            existing=U.objects.filter(username__iexact=username).first()
            if existing:
                self.stdout.write(f'{username}: existing account unchanged (check scope in management).');continue
            user=U.objects.create_user(username=username,password='1234',email=f'{username}@example.invalid',is_staff=False,is_superuser=False)
            p=CoordinatorProfile.objects.create(user=user,full_name=name,role=role);p.qualifications.set(qualifications)
            self.stdout.write(self.style.SUCCESS(f'{username}: created; DEMO ONLY'))

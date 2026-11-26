from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.directory.models import FacultyProfile

class Command(BaseCommand):
    help='Provision fictional local faculty accounts without resetting existing accounts.'
    def add_arguments(self,parser):
        parser.add_argument('--confirm',required=True)
    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEBUG or options['confirm']!='DEMO-ONLY':
            raise CommandError('Requires DEBUG=True and --confirm DEMO-ONLY.')
        records=list(FacultyProfile.objects.select_for_update().filter(status='Active').order_by('faculty_id'))
        if any(not f.user_id and not f.email.lower().endswith('@example.invalid') for f in records):
            raise CommandError('Unlinked active faculty must all have fictional @example.invalid emails. No accounts created.')
        User=get_user_model(); created=0
        for f in records:
            if f.user_id:
                self.stdout.write(f'{f.faculty_id}\t{f.user.get_username()}\tExisting (unchanged)');continue
            base='faculty_'+f.faculty_id.lower(); username=base; n=1
            while User.objects.filter(username__iexact=username).exists():
                n+=1; username=f'{base}_{n}'
            f.user=User.objects.create_user(username=username,password='1234',is_staff=False,is_superuser=False)
            f.save(update_fields=['user']);created+=1
            self.stdout.write(f'{f.faculty_id}\t{username}\tCreated')
        self.stdout.write(self.style.SUCCESS(f'Created {created}; existing {len(records)-created}. Demo only.'))

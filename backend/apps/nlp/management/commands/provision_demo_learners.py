import re
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.directory.models import LearnerProfile

class Command(BaseCommand):
    help='Create local fictional learner accounts only; never reset existing passwords.'
    def add_arguments(self, parser):
        parser.add_argument('--confirm', required=True)
    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEBUG or options['confirm']!='DEMO-ONLY':
            raise CommandError('Requires DEBUG=True and --confirm DEMO-ONLY. Never use with real learners.')
        User=get_user_model(); created=0; skipped=0
        records=list(LearnerProfile.objects.select_for_update().filter(status='Active').order_by('learner_id'))
        if any(not p.user_id and not p.email.lower().endswith('@example.invalid') for p in records):
            raise CommandError('Unlinked active learners must have fictional @example.invalid email addresses. No accounts created.')
        for p in records:
            if p.user_id:
                skipped+=1; self.stdout.write(f'{p.learner_id}\t{p.user.get_username()}\tExisting account (unchanged)'); continue
            base=re.sub(r'[^\w.@+-]','',p.full_name.lower(),flags=re.UNICODE)[:100] or p.learner_id.lower()
            username=base; i=0
            while User.objects.filter(username__iexact=username).exists():
                i+=1; username=f'{base}{p.learner_id.lower()}{i if i>1 else ""}'[:150]
            u=User.objects.create_user(username=username,password='1234',is_staff=False,is_superuser=False)
            p.user=u;p.save(update_fields=['user']);created+=1
            self.stdout.write(f'{p.learner_id}\t{username}\tCreated')
        self.stdout.write(self.style.SUCCESS(f'Created {created}; existing {skipped}. Demo only.'))

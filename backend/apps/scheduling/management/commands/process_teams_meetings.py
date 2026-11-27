import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import close_old_connections
from apps.scheduling.teams import process_one

class Command(BaseCommand):
    help='Process newly confirmed online appointments; ambiguous remote outcomes require manual review.'
    def add_arguments(self,p):
        p.add_argument('--watch',action='store_true')
    def handle(self,*args,**opts):
        if not settings.TEAMS_INTEGRATION_ENABLED:
            self.stdout.write('Teams integration disabled.');return
        self.stdout.write('Teams worker started. No automatic retries of uncertain requests.')
        try:
            while True:
                close_old_connections()
                if process_one(): continue
                if not opts['watch']: break
                time.sleep(5)
        except KeyboardInterrupt: pass

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.directory.models import FacultyProfile
from apps.matching.eligibility import key
from apps.scheduling.models import FacultyWindow
from apps.scheduling.slots import local_time, within_working_hours, MODES


def planned_windows(faculty, now, days):
    """Up to two two-hour windows per working day, within declared hours."""
    zone = ZoneInfo(faculty.time_zone)
    today = now.astimezone(zone).date()
    if not faculty.working_hours_start or not faculty.working_hours_end:
        return
    modes = {key(m) for m in faculty.consultation_modes} & MODES
    if not modes:
        return
    mode = 'either' if len(modes) == 2 else next(iter(modes))
    for offset in range(days):
        day = today + timedelta(days=offset)
        if day.strftime('%A') not in faculty.working_days:
            continue
        start = datetime.combine(day, faculty.working_hours_start)
        end = datetime.combine(day, faculty.working_hours_end)
        if end - start < timedelta(minutes=30):
            continue
        # Early and late portions, with no overlap even on short workdays.
        first_end = min(start + timedelta(hours=2), end)
        pairs = [(start, first_end)]
        last_start = max(first_end, end - timedelta(hours=2))
        if end - last_start >= timedelta(minutes=30):
            pairs.append((last_start, end))
        for a, b in pairs:
            try:
                a, b = (local_time(x.isoformat(), faculty.time_zone) for x in (a, b))
            except ValueError:  # DST gap or ambiguous wall time
                continue
            if a > now and b <= now + timedelta(days=30) and within_working_hours(faculty, a, b):
                yield a, b, mode


class Command(BaseCommand):
    help = 'Seed fictional faculty availability for local development only.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', required=True)
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or options['confirm'] != 'DEMO-ONLY':
            raise CommandError('Requires DEBUG=True and --confirm DEMO-ONLY.')
        days = options['days']
        if not 1 <= days <= 30:
            raise CommandError('--days must be between 1 and 30.')
        dry = options['dry_run']
        now = timezone.now()
        total = skipped = 0
        for f in FacultyProfile.objects.select_for_update().filter(status='Active').order_by('faculty_id'):
            if not f.email.lower().endswith('@example.invalid') or not f.user_id or not f.user.is_active or f.user.is_staff or f.user.is_superuser:
                skipped += 1
                self.stdout.write(f'{f.faculty_id}: skipped (requires linked fictional non-staff account)')
                continue
            try:
                planned = list(planned_windows(f, now, days))
            except ZoneInfoNotFoundError:
                skipped += 1
                self.stdout.write(f'{f.faculty_id}: skipped (invalid time zone)')
                continue
            count = 0
            for a, b, mode in planned:
                # Preserve existing active or archived windows, including busy periods.
                if FacultyWindow.objects.filter(faculty=f, start__lt=b, end__gt=a).exists():
                    continue
                if not dry:
                    FacultyWindow.objects.create(faculty=f, start=a, end=b, kind='available', mode=mode, created_by=f.user)
                count += 1
            total += count
            self.stdout.write(f'{f.faculty_id}: {count} {"planned" if dry else "created"}')
        self.stdout.write(self.style.SUCCESS(f'{total} windows {"planned (no writes)" if dry else "created"}; {skipped} faculty skipped. DEMO ONLY.'))

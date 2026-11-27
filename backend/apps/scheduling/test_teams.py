from unittest.mock import patch
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_booking
from .models import Appointment, TeamsMeeting
from .teams import process_one, on_transition, public_status

@override_settings(DEBUG=True, TEAMS_INTEGRATION_ENABLED=True, TEAMS_TEST_MODE=True,
    TEAMS_TEST_FACULTY_EMAIL='faculty@example.org', TEAMS_TEST_LEARNER_EMAIL='learner@example.org',
    TEAMS_ALLOWED_EMAILS='faculty@example.org,learner@example.org',
    POWER_AUTOMATE_MEETING_URL='https://demo.environment.api.powerplatform.com/flow?sig=fake')
class TeamsTests(TestCase):
    def setUp(self):
        test_booking.BookingTests.setUp(self)
    def confirmed(self):
        pk=test_booking.BookingTests.submit(self)
        self.client.force_authenticate(self.faculty_user)
        r=self.client.post(f'{self.base}{pk}/action/',{'action':'accept'},format='json')
        self.assertEqual(r.status_code,200,r.data)
        return Appointment.objects.get(pk=pk)
    @patch('apps.scheduling.teams.create_remote',return_value=('event','https://teams.microsoft.com/meet/test'))
    def test_creation_once_and_participant_access(self,remote):
        a=self.confirmed();self.assertEqual(a.teams_meeting.status,'queued')
        self.assertTrue(process_one());self.assertFalse(process_one());remote.assert_called_once()
        self.assertEqual(remote.call_args.args[1]['faculty_email'],'faculty@example.org')
        self.assertEqual(public_status(a,self.user)['join_url'],'https://teams.microsoft.com/meet/test')
        self.assertEqual(public_status(a,self.faculty_user)['join_url'],'https://teams.microsoft.com/meet/test')
        outsider=get_user_model().objects.create_user(username='teams-outsider')
        self.assertEqual(public_status(a,outsider)['join_url'],'')
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get(self.base).data,[]) 
        self.assertEqual(public_status(a,self.staff)['join_url'],'https://teams.microsoft.com/meet/test')
    @patch('apps.scheduling.teams.create_remote',side_effect=TimeoutError)
    def test_ambiguous_failure_never_retries(self,remote):
        a=self.confirmed();process_one();self.assertFalse(process_one());remote.assert_called_once()
        self.assertEqual(TeamsMeeting.objects.get(appointment=a).status,'review_required')
    @override_settings(TEAMS_ALLOWED_EMAILS='')
    @patch('apps.scheduling.teams.create_remote')
    def test_unapproved_recipient_blocks(self,remote):
        a=self.confirmed();process_one();remote.assert_not_called()
        self.assertEqual(TeamsMeeting.objects.get(appointment=a).status,'blocked')
    @patch('apps.scheduling.teams.create_remote',return_value=('event','https://teams.microsoft.com/meet/test'))
    def test_cancel_ready_requires_review(self,remote):
        a=self.confirmed();process_one()
        r=self.client.post(f'{self.base}{a.pk}/action/',{'action':'cancel'},format='json');self.assertEqual(r.status_code,200,r.data)
        a.refresh_from_db();self.assertEqual(public_status(a,self.staff)['status'],'review_required');self.assertEqual(public_status(a,self.staff)['join_url'],'')
    @patch('apps.scheduling.teams.create_remote')
    def test_pending_does_not_queue(self,remote):
        test_booking.BookingTests.submit(self);self.assertFalse(TeamsMeeting.objects.exists());self.assertFalse(process_one());remote.assert_not_called()

    @override_settings(TEAMS_TEST_MODE=False, TEAMS_REGISTERED_EMAIL_DOMAINS='')
    @patch('apps.scheduling.teams.create_remote',return_value=('event','https://teams.microsoft.com/meet/test'))
    def test_registered_recipients_not_test_allowlist(self,remote):
        a=self.confirmed()
        a.faculty.email='registered-faculty@example.org';a.faculty.save(update_fields=['email'])
        learner=a.draft.session.learner;learner.email='registered-learner@example.org';learner.save(update_fields=['email'])
        process_one();remote.assert_called_once()
        data=remote.call_args.args[1]
        self.assertEqual(data['faculty_email'],'registered-faculty@example.org')
        self.assertEqual(data['learner_email'],'registered-learner@example.org')
        self.assertFalse(data['subject'].startswith('TEST'))
        self.assertEqual(public_status(a,self.user)['join_url'],'https://teams.microsoft.com/meet/test')
    @override_settings(TEAMS_TEST_MODE=False, TEAMS_REGISTERED_EMAIL_DOMAINS='approved.example.org')
    @patch('apps.scheduling.teams.create_remote')
    def test_registered_domain_restriction(self,remote):
        a=self.confirmed();process_one();remote.assert_not_called()
        self.assertEqual(TeamsMeeting.objects.get(appointment=a).status,'blocked')
    @patch('apps.scheduling.teams.create_remote')
    def test_mode_switch_does_not_redirect_queued_test(self,remote):
        a=self.confirmed()
        with override_settings(TEAMS_TEST_MODE=False): process_one()
        remote.assert_not_called()
        self.assertEqual(TeamsMeeting.objects.get(appointment=a).status,'blocked')

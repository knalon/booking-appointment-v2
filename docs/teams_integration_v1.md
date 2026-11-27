# Milestone 1.4.2A — central Teams organiser, creation only
Compatible with coordinator v1 (does not replace coordinator tests or your local correction).

Prerequisite: approved existing signed Power Automate flow, accepting appointment_id, subject, start_time, end_time, faculty_email, learner_email and returning HTTP 200 JSON success:true, appointment_id, event_id, join_url. All timestamps are UTC. No new Entra app, participant calendar reads, or SMTP.

Back up source and database. Merge backend/frontend/docs. Run manage.py check, migrate, makemigrations --check --dry-run, and test apps.coordinator apps.scheduling apps.matching apps.nlp.test_nlp with integration disabled. New migration scheduling.0004_teamsmeeting. Five new tests mock the network. npm run build.

Add to existing PROJECT ROOT .env (not frontend):
TEAMS_INTEGRATION_ENABLED=True
TEAMS_TEST_MODE=True
POWER_AUTOMATE_MEETING_URL=<private signed URL>
TEAMS_TEST_FACULTY_EMAIL=<approved address 1>
TEAMS_TEST_LEARNER_EMAIL=<approved address 2>
TEAMS_ALLOWED_EMAILS=<approved address 1>,<approved address 2>

Use two distinct controlled addresses, DEBUG=True for test mode. Never commit .env or share the URL. Test mode creates a REAL meeting but routes invitations only to the two approved addresses. Local demo participant accounts see status, not the test join link; management can see the link. Do not use the Anyone trigger unless institution authorises it. Restart Django and run `python manage.py process_teams_meetings --watch` in another backend terminal. Stop with Ctrl+C. Without --watch it drains the queue and exits. Confirm a NEW future online appointment. Worker polls every 5 seconds. Appointment page refreshes every 15 seconds. No old appointments are automatically backfilled. Face-to-face appointments don't create meetings.

Live mode (TEAMS_TEST_MODE=False) uses master profile emails, only when BOTH are explicitly allowlisted; enable only after institutional approval and controlled testing. Do not switch mode with queued jobs. Keep one worker for the prototype. No automatic retry after a network error, malformed response or worker crash: inspect Power Automate run history and organiser calendar; a 502 may have created a meeting. `sending` after a crash and `review_required` require manual intervention; no self-service reconciliation/retry in this release. `blocked` means no HTTP request was sent. Fix config and use a new test appointment; do not directly reset unknown jobs. Cancellation/reschedule after a meeting was created flags manual review and hides the old link; organiser must manually cancel/update the external event. No external cancellation/update flow has been tested. A pending proposal may leave its old external meeting active until reconciled. Internal appointment remains authoritative. End-to-end exactly-once is not guaranteed by the existing Power Automate flow; the app avoids automatic replay. Meeting invitations and lobby access must be tested with actual attendees.

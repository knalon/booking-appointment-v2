# Milestone 1.3 — Appointment booking and in-app notifications

Apply after Integrated Conversational Scheduling v2. Stop servers and back up the project/database, merge backend/frontend/docs, then from backend run:

```
python manage.py check
python manage.py migrate --plan
python manage.py migrate
python manage.py makemigrations --check --dry-run
python manage.py test apps.scheduling apps.matching apps.nlp.test_nlp
```

From frontend: `npm run build`, then `npm run dev`. Start Django with `python manage.py runserver`. New migration: scheduling.0002_appointments. No reseed, dependencies or email credentials required. Existing confirmed consultation, recommendation and schedule JSON are immutable historical records, not the current booking status. Current status is stored in Appointment; audit history in AppointmentEvent; private notification rows in Notification.

## Workflow

1. Learner chooses a slot and clicks Submit appointment request. The backend validates the exact saved selection, current eligibility, working hours, published window, busy periods, mode and overlaps. The initial selection alone is not a hold.
2. A pending request holds a 30-minute interval for both participants until approved, declined, cancelled or expired. Expiry is the earlier of 24 hours after submission and the scheduled start. Duplicate submissions for an active request return the existing appointment. Faculty and learner profile row locks serialize reservation writers, including availability changes using the existing faculty row lock. Scheduling excludes active holds and confirmed appointments. No overlapping reservations, including partially overlapping intervals. Adjacent intervals are allowed.
3. Faculty sees a bell badge and My appointments. Accept confirms; decline releases. Faculty can propose a different published compatible 30-minute slot. The old slot is released and new one held pending learner acceptance. Learner may decline or cancel. Both participants and management may cancel before start. Faculty or management may mark completed/no-show after end. Management sees all appointments; faculty and learners only their own. There is no separate coordinator role in this patch.
4. Bell notifications are stored in the database; polling every 15 seconds while signed in, unread count, individual read and mark-all-read. Clicking a notification opens My appointments and highlights the item. Latest 50 notifications and latest 100 appointments shown. No email, SMS, push, WebSocket or meeting link integration. No automated reminders. Active holds expire logically at deadline even if no one is online; status/audit/notification are materialized on next appointment or notification read by a participant or management. No background worker.
5. Faculty calendar displays amber pending and blue confirmed appointment cards. Availability changes that overlap reservations are conservatively blocked. Management review is available; automated coordinator escalation and dedicated coordinator workspace are not implemented.

## Manual testing

Use separate browser profiles for learner, assigned faculty, management. Confirm a consultation, choose an existing slot, submit, inspect faculty notification and calendar, accept, inspect learner notification and appointment status. Try another learner selecting an overlapping slot before the first submission, then submitting afterward; second request must fail. Check cancel/decline release, reschedule acceptance, expiry, unread persistence, no cross-account access, and existing NLP/availability. Use a future window and active linked faculty accounts. MySQL concurrency should be tested using two simultaneous clients; automated overlap tests are sequential, not a load test. No production policy for cancellation notice, escalation or approval overrides has been established.

## Verification

Python compilation and JSX parsing performed; integration tests and Vite build require local verification. Eight new booking tests are supplied.

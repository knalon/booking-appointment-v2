# Coordinator Accounts & Workspace v1 — Milestone 1.4.1

## Baseline
Apply after Appointment Booking & Notifications v1 (and the previously installed incremental patches). Stop Django and Vite and back up the project and database. Extract at the project root, replacing matching files. This does not change NLP prompts, matching weights, consultation duration, or booking approval policy.

## Install (backend PowerShell, activated venv)

```powershell
python manage.py check
python manage.py migrate --plan
python manage.py migrate
python manage.py makemigrations --check --dry-run
python manage.py provision_demo_coordinators --confirm DEMO-ONLY
python manage.py test apps.coordinator apps.scheduling apps.matching apps.nlp.test_nlp
python manage.py runserver
```

New migrations: `coordinator.0001_initial`, then `scheduling.0003_review_notifications` (dependency order enforced). The second migration makes the appointment target optional and adds a review case target to Notification, with a database constraint requiring exactly one target. Existing appointment notifications remain unchanged. No new libraries, no reseeding of faculty or learners.

Frontend PowerShell: `npm run build`, then `npm run dev`. Hard-refresh browsers. Use separate browser profiles for each user role.

## Sign-in

- Management: `/` (existing staff account). New tabs **Consultation reviews** and **Coordinator accounts**.
- Coordinator or Programme Manager: `/coordinator`. The demo provisioner creates `coordinator_<lowercase qualification code>` for each active qualification; e.g. `coordinator_dsd` for DSD. `programme_manager_demo` covers all active qualifications at provisioning time. Newly created demo users use password `1234`. This requires DEBUG=True and explicit DEMO-ONLY; never use these credentials in production. Existing usernames are skipped, never overwritten. Review their scopes in Management. No public role self-registration.
- Learner: `/learner` (existing account), new **Review messages** tab. Request coordinator assistance from a confirmed consultation's scheduling panel.
- Faculty: `/faculty` (unchanged).

Only a superuser may create/edit/archive coordinator or Programme Manager profiles in React. The normal account-creation form enforces Django password validators, non-staff users, and active qualifications. Editing an account changes name, role, status and qualification assignment; password resetting is not part of this patch. Archived profiles cannot use coordinator APIs; old case notifications are filtered against current access. Case ownership is released when management removes a coordinator's scope or changes their role/status.

## Review workflow

1. The server opens a review case for urgent confirmed consultations, support or administrative routing, failed academic matching, no compatible scheduling slots, declined or expired appointments, or an explicit learner assistance request. Cases are keyed to the confirmed draft, not the conversation transcript; repeated signals do not duplicate cases.
2. A matching qualification coordinator receives an in-app notification. If there is no assigned active coordinator, the superuser receives it instead. A review case created before an account was provisioned will be visible in the queue but old alerts are not replayed.
3. The coordinator opens a case and claims it. Other coordinators in the qualification can read but cannot change a claimed case. An owner or management can release it.
4. Internal notes are visible only to scoped staff. Learner-facing messages, verified academic faculty suggestions and resolution summaries are stored in history and notify the learner. A suggestion is advice, not an allocation or a booking. Live eligibility and academic threshold are rechecked when sending it. The learner still uses normal scheduling and faculty approval.
5. Escalation requires a reason and sends a notification to the qualification's Programme Manager(s) and superuser(s). Programme Managers use the same workspace and can act on escalated cases. Coordinators cannot resolve escalated cases. A resolution requires a learner-facing summary. Resolved cases retain history; an explicit new learner request or a different system trigger can reopen them. Cases are not silently closed when a booking succeeds: the review owner checks current appointment/scheduling status and resolves them.
6. Coordinator appointment oversight is read-only. Shared faculty availability editing, booking overrides, and automatic support-team assignment are intentionally not delegated. Management retains its previous permissions; existing faculty approval/cancellation remains unchanged. Coordinator cases use the immutable qualification and require that it still matches the learner's current qualification; changed/unassigned qualification cases require management oversight.
7. Both the review queue and the notification bell poll every 15 seconds. **Refresh / scan recent requests** explicitly checks up to the latest 200 scoped confirmed requests, including existing historical data and expired holds. Existing expiry processing on learner/faculty/admin access also opens cases when it expires a hold; no independent worker. Queue display is capped at 200 cases, appointment oversight at 100, learner review messages at 100 and existing notification list at 50. Not intended as full production-scale paging.

## Manual integration checks

- Provision demo accounts; choose an actual qualification code from the command output. Log in as a learner with the same qualification and request assistance on a confirmed consultation.
- Verify coordinator bell, unread count, case opening, qualification scoping and case claim. Sign in as a second qualification coordinator and verify no access.
- Add an internal note; confirm it is absent from learner Review messages. Send learner message; verify notification opens the case and marks it read.
- Try suggesting a valid faculty; verify the learner sees the suggestion but no appointment is created. For no-match cases, the suggestion selector may be empty.
- Escalate with a reason; verify Programme Manager receives notification and can resolve. Learner sees the resolution. Confirm case history remains available.
- Verify appointment oversight is scoped and read-only; existing learner/faculty booking flow and notifications still work.
- In Management, create an account with a strong password, set qualification scope, archive/restore the profile, and verify the archived account is denied.
- Test historical scan; verify repeated refresh does not create duplicate cases. Test urgent and no-slot cases. Confirm `makemigrations --check --dry-run` is clean.

## Verification and limitations

Python compilation and TypeScript JavaScript/JSX syntax parsing performed on reconstructed source. Twelve coordinator regression tests are included; Django/MySQL integration tests and Vite production build were not runnable in the packaging environment. Expected 73 total if the previous suite had 61; check actual discovery. No email, WebSockets, automatic escalation timers, direct learner reply within review thread, external support connector, account password reset, or production identity provider integration. No live MySQL concurrency or migration run has been performed. The initial case service is an operational review workflow, not an automatic exception-to-booking override. Back up and verify all tests locally before proceeding.

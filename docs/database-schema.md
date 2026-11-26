# Initial database schema

- `AcademicProgramme`: canonical programme catalogue.
- `AcademicModule`: canonical module catalogue.
- `FacultyProfile`: one row per faculty ID; optional link to an authenticated user.
- `FacultyExpertise`: one row per faculty/module mapping, including topics, level, verifier, review date and consultation eligibility.
- `LearnerProfile`: one row per learner ID; optional link to an authenticated user.

Operational data (requests, availability, bookings, approvals and feedback) is deliberately excluded from this first data-foundation milestone.

# Faculty–Learner Appointment Agent — Project Frame

This repository is the initial project scaffold for a Django + React + MySQL application.

## Stack
- Backend: Django + Django REST Framework
- Frontend: React + Vite
- Database: MySQL (`utf8mb4`)
- Development authentication: Django authentication for local testing
- Future institutional authentication: integrate the institution's SSO/identity provider without changing profile IDs.

## Important scope
This is a project frame, not a completed booking system. The CSV endpoint currently receives files but does not import them. Matching, availability, booking, approval, notifications and AI orchestration are intentionally not implemented yet.

## Data files
Use `faculty_v4.csv` and `learners_v4.csv` from the accompanying dataset exports.
- Faculty expertise mappings are JSON encoded in one CSV cell to avoid delimiter ambiguity.
- English is mandatory in each faculty language list and learner preferred-language list.
- Do not put passwords or authentication secrets in either CSV.

## Backend setup
1. Create and activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` in the repository root and configure MySQL.
4. Create the MySQL database using `utf8mb4`.
5. From `backend/`, run:
   - `python manage.py makemigrations`
   - `python manage.py migrate`
   - `python manage.py createsuperuser`
   - `python manage.py runserver`

## Frontend setup
From `frontend/`:
1. `npm install`
2. `npm run dev`

## Initial API routes
- `GET /api/directory/faculty/` — admin-only faculty directory
- `GET /api/directory/learners/` — admin-only learner directory
- `POST /api/imports/faculty/` — CSV upload receipt placeholder
- `POST /api/imports/learners/` — CSV upload receipt placeholder

## Next implementation tasks
1. Implement robust CSV preview and validation.
2. Implement transactional upsert for faculty and learners.
3. Add data-import batch logs and row-level error reports.
4. Add profile-to-auth-user linking for development accounts.
5. Add Stage A request/session models and APIs only after the directory import is stable.

## Security note
The `.env.example` values are placeholders. Never commit `.env`, real credentials, or production secrets.

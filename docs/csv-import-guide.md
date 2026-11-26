# CSV Import Engine — Milestone 0.4

## What this patch adds
- Admin-only CSV preview endpoints for faculty and learners.
- Exact header validation against the v4 templates.
- Row-level validation, including required English language.
- Duplicate ID and email checks within each uploaded file.
- JSON expertise mapping validation.
- Preview batches saved in MySQL for 24 hours.
- Explicit confirmation endpoint.
- Transactional all-or-nothing import.
- Upsert by Faculty_ID / Learner_ID (existing IDs are updated, not duplicated).
- Faculty expertise imported into `FacultyExpertise` relational rows.
- Programme and module catalogues populated from the CSVs as needed.
- Faculty taught-module names without a matching expertise module code are preserved in `additional_modules_taught`; the importer does not invent official module codes.

## Apply the patch
Copy the contents of this patch into the matching locations in your existing project, allowing files to merge/overwrite when prompted. Do not replace `.env`, your local database, or the whole project folder.

## Run migrations
From `backend/` with the virtual environment active:

```powershell
python manage.py makemigrations directory data_imports
python manage.py migrate
python manage.py check
```

The patch includes migrations for the additional faculty taught-module field and the import-batch table. If Django says there are no model changes, that is fine if the migration files are already present and applied.

## Endpoints
All endpoints require an authenticated Django staff user (`is_staff=True`).

- `POST /api/imports/faculty/preview/` — multipart form field `file`
- `POST /api/imports/learners/preview/` — multipart form field `file`
- `POST /api/imports/batches/<batch_id>/confirm/` — JSON body `{}`
- `GET /api/imports/batches/<batch_id>/` — inspect batch status

## Safe testing order
1. Log in to Django Admin in the same browser session.
2. Open `/api/imports/faculty/preview/` and upload `faculty_v4.csv` using the `file` field.
3. Review the preview response. Do not confirm if errors are present.
4. Copy the returned `batch_id`.
5. POST `{}` to `/api/imports/batches/<batch_id>/confirm/`.
6. Repeat with `learners_v4.csv` at `/api/imports/learners/preview/`.
7. Confirm the learner batch only after reviewing its preview.

## Important behaviour
- The import is all-or-nothing. A file with validation errors cannot be confirmed.
- Existing profile IDs are updated. Profiles omitted from a CSV are not deleted or deactivated.
- For a faculty ID included in the CSV, its expertise mappings and programme/module links are synchronised to that row's uploaded data.
- This is the backend API milestone. A polished React upload/preview screen will be a later frontend task.
- The fabricated CSV files are development data only. Do not upload them as real institutional records.

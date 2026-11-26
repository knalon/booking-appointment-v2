# Academic Master Data Patch v1 (0.4.1)

Prerequisite: original project frame and CSV Import Patch v1, with directory migrations 0001 and 0002 applied. Back up the project and MySQL database first. Stop Django. Merge the patch at the project root; do not replace the whole backend directory, delete migrations, or overwrite .env. No additional dependencies.

From backend with the existing venv active:

    python manage.py check
    python manage.py migrate --plan
    python manage.py migrate
    python manage.py runserver

Open http://127.0.0.1:8000/admin/master-data/ while signed in as the Django administrator. Import and confirm programmes_v1.csv, modules_v1.csv, faculty_v5.csv, learners_v5.csv in that order. Old v4 CSVs and old pending previews are incompatible. The directory migration backfills known programme codes and reconciles unambiguous legacy module names. Unresolved legacy names remain visible until a faculty snapshot explicitly replaces them. Never delete the database. Existing primary keys/auth links and confirmed import batch history are retained. Catalogue codes are stable; API DELETE archives instead of deleting.

**Important:** faculty and learner rows are full snapshots for their respective IDs, not field-level patches. Included profiles, expertise and relationships can change; omitted IDs are retained. If you amended F001 teaching experience to 9 locally, the supplied v5 file contains the original 8; update that value in the CSV before confirming if you want to keep your amendment. Save a database backup before installing; the revised dataset is synthetic, not an export of your local database. Programme-module associations are inferred from synthetic existing records, not a real academic curriculum. Automation was assigned AU301 because it was a teaching-only subject in the previous data. Original example.edu emails were replaced with example.invalid for safe testing. Programme/module catalogue imports use code-based upserts and replace links on included module rows. Archived catalogue records remain referencable for historical data; future matching must exclude inactive entities.

Admin UI supports CRUD (archive/restore for catalogue) via Django Admin, CSV preview/confirm and export, recent batch history. The React frontend remains unchanged. Staff API access follows the existing development project's IsAdminUser policy; finer institutional RBAC is future work. Imports reject invalid files as a whole, check stale previews and use atomic transactions. Do not edit the DB concurrently during this development import. The legacy additional_modules_taught field is retained deliberately for reconciliation; a valid faculty import clears it for included rows. Faculty CSV export is blocked if any unresolved legacy names remain. For production, configure appropriate identity, roles, audit and retention policies; CSV formula injection protections and concurrent admin editing controls need further hardening.

API: POST /api/imports/{programmes|modules|faculty|learners}/preview/ (multipart file); POST /api/imports/batches/{uuid}/confirm/ (JSON); GET /api/imports/{dataset}/export/. Catalogue endpoints GET/POST /api/directory/programmes/ and /modules/; GET/PATCH/DELETE /api/directory/{programmes|modules}/{code}/. DELETE archives. PATCH is_active=true restores.

Checks: Python syntax and cross-file ID/reference validation performed during packaging. Django and MySQL runtime not available in packaging environment. Run supplied tests on a disposable test database with appropriate privileges: python manage.py test apps.data_imports. Expected seeded totals on a clean database: 10 programmes, 31 modules, 30 faculty, 300 learners, 70 expertise rows. Existing additional records may increase totals. Import same file twice: second preview should show only unchanged rows. Verify F001 has PY101 and PF101 in modules taught, with only PY101 expertise approved.

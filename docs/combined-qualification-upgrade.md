# Combined Professional Education + Qualification Update (0.4.4)

Target: Academic Topic Catalogue Patch v1 (directory 0004, data_imports 0003), with earlier patches already installed. No separate Professional Education or Qualification Terminology patch required.

1. Stop Django. Back up project and MySQL database.
2. Merge backend, data, docs into project root; replace matching files, never delete directories. Keep .env, virtual environment, frontend, existing migrations.
3. From backend with virtual environment activated: 

    python manage.py check
    python manage.py migrate --plan
    python manage.py migrate
    python manage.py makemigrations --check --dry-run

Expected migrations: directory.0005_professional_curriculum, directory.0006_qualification_terminology, data_imports.0004_curriculum_import, data_imports.0005_qualification_terminology (dependency order may vary). If migration fails, stop; MySQL DDL may not roll back.

4. To replace the old fictional data with the new professional qualification catalogue, run once (destructive to existing master data and manual amendments; requires DEBUG=True and no linked profiles):

    python manage.py reseed_professional_data --confirm REPLACE-FICTIONAL-DATA

5. python manage.py runserver
6. Open Django Admin, navigate to Master Data Management and Qualifications. Expected 10 qualifications, 52 modules, 64 curriculum assignments, 261 topics, 30 faculty, 94 expertise mappings, 300 learners.

Old pending import previews expire; use the new CSV formats. Existing historical migrations deliberately retain former terminology. Legacy directory API aliases remain. No new dependencies or frontend changes. No database reset needed. Local runtime tests: python manage.py test apps.data_imports (requires test database permissions). Static checks only; Django/MySQL runtime not available in packaging environment.

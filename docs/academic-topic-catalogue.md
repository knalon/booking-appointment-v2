# Academic Topic Catalogue patch v1

Prerequisites: Academic Master Data Patch v1 and Admin Navigation Patch v1 already installed. Back up code and MySQL. Merge backend, data and docs into project root. Run `python manage.py check`, `python manage.py migrate --plan`, `python manage.py migrate`, `python manage.py runserver` from backend.

The migration creates topic rows from existing expertise names and links them without changing faculty profiles, approvals or original topic text. Existing preview batches expire. Topic codes are stable generated identifiers. The supplied fictional catalogue has 108 topics across 31 modules. It combines original module tags and expertise topics; not an official curriculum.

In Django Admin > Master Data Management, select Topics and preview topics_v1.csv. Confirm only if valid. Existing custom topic names or duplicate codes can require reconciliation; do not delete existing records to force an import. Faculty v6 uses topic codes in the existing `topics` JSON array, and old name-based faculty v5 files are no longer accepted. Export current faculty data after migration to preserve local edits; the supplied v6 is optional for reseeding and will overwrite included profile fields. Programme/module/learner formats are unchanged.

Manage topics from Directory > Academic topics or the module list's Manage topics link. Archive instead of deleting. Faculty profile includes expertise inline; standalone expertise edit filters topics to the selected module. Backend validates module membership. Archived topics remain linked historically; future matching must filter active topic/module/faculty and approved expertise. Omitted expertise mappings are revoked rather than deleted; include all mappings in future imports for clean round trips.

Local tests: `python manage.py test apps.data_imports` (requires MySQL test database privileges). No React changes. No new dependencies.

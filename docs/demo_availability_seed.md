# Demo availability seed v1
Requires Faculty Accounts & Workspace v1 and migrated scheduling tables. Run from backend with DEBUG=True, after provisioning demo faculty accounts.

    python manage.py seed_demo_availability --confirm DEMO-ONLY --dry-run
    python manage.py seed_demo_availability --confirm DEMO-ONLY

Optional --days 7 (default 30, range 1–30). Uses each fictional active faculty's local working days, hours and supported modes. Up to two windows of up to two hours per working day, at the beginning and end of working hours. Skips past starts, invalid zones and overlaps with any existing window (including archived ones). Existing records are never edited or deleted. Re-running on the same dates does not duplicate records; later runs extend the rolling horizon. Does not create busy periods or bookings. Demo availability is synthetic, not verified actual availability. No migration or frontend change.

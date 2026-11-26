# Matching test compatibility fix v1
Requires Faculty Recommendation & NLP Refinement v2.
Replace backend/apps/matching/tests.py with this file. No production code or database changes.
The previous fixture used FIELDS to initialize new fields to None but never set topic_resolution; clean_draft correctly rejected the topic code with no resolution. The fixture now uses schema 1.1, exact resolution and normal urgency. Two regression tests cover legacy snapshots and strict current snapshot validation.
Run python manage.py test apps.nlp.test_nlp apps.matching from backend. Expected discovery: 20 tests. Actual pass count must be verified locally. Python syntax checked; Django unavailable in build environment.

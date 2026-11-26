# Conversational NLP Classification & Routing Refinement v4 (1.1.3)

Baseline: Conversational NLP Quality Refinement v3 plus Faculty Matching Test Fix v1. Merge backend/, frontend/, docs/ into the existing project after backing up code and database. No migration, reseeding, dependencies or .env changes. Restart both servers and use a new conversation. Run `python manage.py check`, `python manage.py test apps.nlp.test_nlp apps.matching`, and `npm run build` in frontend.

## Routing
- academic + coursework or learner_project: faculty matching, provided current enrolled module and approved expertise are valid.
- technical + coursework or learner_project: same matching criteria. This uses existing verified module/topic expertise as a proxy for practical assistance; dedicated project troubleshooting accreditation is not included.
- technical + institutional_system: support/coordinator review flag only.
- other + administrative: coordinator review flag only.
- technical project with explicitly no suitable enrolled module (null module/topic, no_match resolution): coordinator review flag; no artificial module assignment.
- unrelated requests remain redirected and do not change saved draft.

The server validates type/scope and applies conservative English consistency checks; the provider still handles semantics, including multilingual cases. Preference-only turns preserve established purpose unless explicit problem evidence or a substantive correction is detected. Ambiguous technical scope is clarified. Supported alternative languages use OR, not AND. Unknown languages require clarification. A new final JSON uses schema 1.2, with request.consultation_scope, top-level routing, preferred_languages (empty means flexible), language_match_policy=any. Original preferred_language string remains for compatibility. Existing confirmed snapshots are immutable; legacy non-academic requests remain review-only because they have no confirmed scope. Start a fresh request to correct them; existing runs are not silently recalculated. Old academic requests remain supported subject to current eligibility and validation.

## Checks
Seven new regression tests, expected 31 total with prior fixes. Python compilation and standalone routing/policy/controller checks performed. Django/MySQL integration, live model behaviour and React build must be checked locally. No OpenAI calls during automated mocked/unit tests. No availability, booking or coordinator notification implementation.

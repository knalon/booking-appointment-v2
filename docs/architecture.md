# Architecture

## Responsibility boundaries
- React: user interface and client-side interaction.
- Django REST API: validation, permissions and orchestration.
- Directory domain: faculty, learners, programmes, modules and expertise.
- Data imports: CSV upload, preview, validation and transactional upsert.
- Future domains: appointments, scheduling, matching, notifications and audit.

## Identity design
Profile records have optional one-to-one links to Django auth users. Fabricated profile data can be imported before institutional identity integration. For development, create local test users separately; never infer passwords from CSV rows. Later, map institutional SSO identities to the same profile IDs.

## Data modelling
Faculty expertise is a separate relational table, not a free-text matching rule. The CSV uses a JSON-encoded `Expertise_Mappings` cell as a transport format; the importer should normalise each mapping into `FacultyExpertise` rows.

# Provenance

Provenance is a first-class scientific graph. An evidence-bearing assertion will link to a source document/article and the most precise available location (page, section, paragraph, table, figure, coordinates, and source text). It also records the responsible human or AI actor, model/provider, prompt and model versions, algorithm/task version, timestamp, confidence, verification state, and downstream uses.

Audit history answers who changed an application record and when. Scientific provenance answers why a scientific claim exists and what evidence supports it. They are related but not interchangeable.

Corrections create append-only change events carrying previous value, new value, reason, and actor. Normal application operations must not erase history.

## Persisted ledger foundation

Migration `20260810_0005` implements four separate append-only record families:

- `prompt_versions` stores immutable, monotonically numbered prompt templates and output schemas per organization.
- `ai_runs` captures the exact prompt version, provider/model/version labels, parameters, input and output snapshots, status, usage, review, and responsible human initiator. It records runs from mock/fixture providers today; it does not invoke a paid provider.
- `scientific_provenance` links a subject to an optional source and precise structured locator, method/version, human or AI actor, confidence, and verification state.
- `audit_events` records application changes with actor, before/after snapshots, reason, and optional review scope.

ORM mutation guards reject updates and deletes for all four families. Application services expose append and tenant-scoped read operations only. Corrections therefore append a new record or audit event; they never rewrite the historical row.

Actor constraints are explicit. Human provenance points to an active same-organization membership. AI provenance points to an AI run in the same organization and review. System provenance is reserved for internal services. Generic subject/source identifiers make the ledger usable across later scientific domains without collapsing those domains into the provenance schema.

## Extraction provenance

Study-family links record their method, actor, reason, confidence, and source evidence. Manual extraction values use the same scientific provenance ledger as documents and screening: each value records its Article or Document source, field locator, selected evidence text, manual method version, and extractor actor. Verification does not replace either run. It records canonical agreement or an explicit conflict, and adjudication appends a human-verified provenance record linked to the conflict while retaining both original evidence snapshots.

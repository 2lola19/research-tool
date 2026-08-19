# ADR-033: Production AI Provider Integrations, Routing, and Cost Governance

## Status

Accepted for Phase 34.

## Context

The AI foundation preserves immutable model/prompt versions and append-only attempts, but its only
executable provider is the deterministic mock. Production adapters must not import vendor SDKs,
expose credentials, silently change a task's model, or turn a model response into canonical
scientific state. Usage and spend controls also need to remain reconstructable across retries and
tenant boundaries.

## Decision

- OpenAI Chat Completions, Anthropic Messages, and Gemini Generate Content are implemented as
  provider-protocol adapters behind a small HTTP transport. Endpoints are fixed by adapter; callers
  cannot supply arbitrary URLs. The transport bounds timeout and response bytes and classifies
  timeout, rate-limit, unavailable, permanent, invalid-response, and policy failures without
  persisting response bodies from error messages.
- Live provider execution requires explicit configuration enablement and an environment-backed
  provider secret. The deterministic mock remains the default. Provider/model allowlists and
  structured-generation capability checks are applied before a run is created. Task routing is
  deterministic and pins provider/model identity in the immutable run policy snapshot.
- Fallback between providers is disabled. A missing provider, disallowed model, missing live
  pricing, open circuit, or exhausted tenant budget fails closed; it never silently switches to a
  stronger, cheaper, or different model.
- Provider usage is normalized into the existing append-only AI attempt records. Costs use exact
  decimal arithmetic only when versioned input/output prices and provider usage are present;
  otherwise cost remains explicitly unknown. Tenant monthly token/cost budgets and provider/model
  circuit state are derived from scoped attempt history and retained in the run policy snapshot.
- Adapters receive bounded structured input and no tools, retrieval, filesystem, shell, browser, or
  database authority. Scientific validators and existing human acceptance/domain services remain
  the only paths to consequential scientific writes.

## Consequences

The existing AI schema is sufficient for this phase; no second cost ledger or provider-specific
scientific table is introduced. The deployment must configure allowlisted model identifiers and
pricing before enabling a paid provider. Live credentials, external network behavior, provider
terms, and PostgreSQL concurrency remain deployment validation gates. The selected model is used
for normal implementation and execution; autonomous model switching is not part of the program.

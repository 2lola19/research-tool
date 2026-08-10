# AI Architecture

Domain code calls task-oriented services such as screening, extraction, and adjudication. Those services depend on the `AIProvider` protocol and a versioned prompt registry. Vendor SDKs are infrastructure adapters only.

The default `MockAIProvider` returns deterministic structured output and requires no network or credentials. Real providers will be selected by configuration and every scientific AI run will record provider, model/version, prompt/version, parameters, schema, timestamps, status, and usage.

Prompts live in a versioned registry, not arbitrary route handlers. Schemas permit `NOT_REPORTED`, `UNCLEAR`, `NOT_APPLICABLE`, and `NEEDS_REVIEW`. Deterministic calculations are prohibited from using AI.


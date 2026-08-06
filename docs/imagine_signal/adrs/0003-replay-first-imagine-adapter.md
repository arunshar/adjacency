# ADR 0003: Make replay the default for the Imagine adapter

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-08-05 |
| Author | Arun Sharma |
| Deciders | Engineering lead and Imagine API owner, TBD |
| Reviewers | Security, privacy, SRE, finance |

## Context

Image generation is paid, non-deterministic, provider-dependent, and returns media that cannot be safely represented as ordinary JSON metadata. Local tests and review demos must not depend on credentials, provider uptime, temporary URLs, current aliases, or repeated charges.

The repository already uses content-addressed JSON fixture replay. The current implementation scans request data for secret-shaped fields, but response scanning and binary asset handling need to be added for Imagine.

## Options considered

### Option A: Call the live API by default

Advantages:

- Always shows current model behavior.
- Little fixture management.

Disadvantages:

- Paid and non-reproducible tests.
- Credential and outage dependency.
- Accidental calls on fixture misses.
- Temporary URL and data-retention risk.

### Option B: Mock the SDK response in unit tests only

Advantages:

- Fast and simple.
- No binary fixture format.

Disadvantages:

- Does not prove real request and response mapping.
- Misses media integrity, cost, moderation, and temporary-URL behavior.
- Easy for mocks to drift from the provider.

### Option C: Record intentionally, replay by default, and store media by digest

Advantages:

- Credential-free deterministic tests and demos.
- Real provider contract can be recorded once.
- Media bytes, metadata, and cost remain verifiable.
- Clear separation between provider proof and local proof.

Disadvantages:

- Requires a binary fixture store and sanitization.
- Fixtures must be refreshed when the contract or pinned model changes.
- Non-sensitive assets are needed for committed examples.

## Decision

Choose Option C.

Create separate clients:

- `FixtureImagineClient`, which has no live transport and is the default.
- `RecordingImagineClient`, which exists only under an explicit record flag and approved cost cap.

Store sanitized JSON control metadata under the canonical request hash and media bytes under the media SHA-256. Scan both request and response metadata. Never commit credentials, authorization headers, raw base64, signed URLs, or confidential production prompts and assets.

A fixture miss is terminal in replay mode. It never activates live transport.

## Consequences

### Positive

- Tests, demos, review, and paper artifacts remain reproducible and inexpensive.
- Provider behavior and media integrity are separately inspectable.
- Model changes create explicit fixture and claim updates.

### Negative

- Recording needs an operator checklist.
- Large media requires storage discipline.
- A fixture proves a provider interaction at one time, not current availability.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Secret in provider response | Allowlist response fields and run recursive scan |
| Corrupt or mismatched media | Verify digest, length, type, and dimensions on record and replay |
| Unknown cost appears free | Use nullable or explicit cost status; block paid escalation |
| Temporary URL expires | Decode or download immediately; never use URL as identity |
| Concurrent record corrupts fixture | Atomic metadata and blob writes plus request-level lock |
| Sensitive media committed | Non-sensitive fixture policy and review gate |

## Implementation notes

Keep the provider SDK or HTTP transport outside the deterministic core. Add network-blocked integration tests. After a live recording, remove the key and rerun the complete replay path before accepting the fixture.

## Review trigger

Revisit if xAI provides a deterministic test environment, signed fixture service, or a production Files API contract that changes the preferred media persistence boundary.


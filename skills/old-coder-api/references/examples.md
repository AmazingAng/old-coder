# Compact review examples

These examples calibrate decisions, not current facts about third-party APIs. The excerpts are intentionally small enough to resemble normal route or OpenAPI review work.

## Existing public OpenAPI diff: safety versus compatibility

```text
41  -        display_name: { type: string }
41  +        name: { type: string }
73         post:
74  +        parameters:
75  +          - { name: Idempotency-Key, in: header, required: true }
76           operationId: createTransfer
```

```text
## API review: transfer API
Scope: public · existing

### Breaking changes (blocking)
- `display_name` was renamed, so typed consumers lose a field — openapi.yaml:41
  Fix: add `name` and keep populating `display_name`.
- A formerly valid request now fails without a new header — openapi.yaml:75
  Fix: accept the key optionally in this version, generate it by default in official
  SDKs, and require it only in a new major contract or new safer operation.

### Verified context

- Idempotency ✓ — supplied keys are atomically claimed with the transfer; repeats replay the original status and body, a different request hash is rejected, and records survive the documented retry window — transfers/idempotency.ts:52-81.
- Blast radius ✓ — `createTransfer` inherits write-tier limits, recovery headers, and a per-consumer killswitch — gateway/limits.yaml:88.

### Gates: Boring ? (unverified: route convention not in diff) · Compatibility ✗ · Authentication ? (unverified: not in diff) · Authorization ? (unverified: not in diff) · Idempotency ✓ (verified contract) · Blast radius ✓ · Pagination N/A (not a collection) · Expensive fields ? (unverified: response cost not in diff) · No implementation leakage ? (unverified: response shape not in diff)
```
The submitted diff passes Idempotency but fails Compatibility. Making the key optional preserves compatibility but leaves duplicate protection incomplete until a new operation or major contract can require it. Record both states explicitly: compatibility outranks the tempting retroactive fix, but the additive migration is not the final idempotency solution.

## Greenfield proposal: fix the resource model first

Context: report exports are durable, long-running product resources, and `rows` has no fixed upper bound.

Input excerpt (line-numbered `proposal.yaml`):

```text
12  GET /reports/export
14    api_key: query string
16    tenant_id: query string
18    response: { rows: [...], billing_profile: {...} }
```

```text
## API review: report export proposal
Scope: public · greenfield

### Security boundary
- A query-string credential leaks through URLs and logs — proposal.yaml:14
  Fix: use a scoped, revocable API key in the Authorization header.
- The caller selects a tenant without a stated principal check — proposal.yaml:16
  Fix: derive the tenant from the credential or verify membership server-side.

### Incident risk
- The export is an unbounded synchronous read that will be called in loops — proposal.yaml:12
  Fix: model exports as `POST /exports` plus `GET /exports/{id}`, rate-limit creation,
  and paginate the exported items with a server-provided `next_page`.

### Ergonomics
- `billing_profile` makes every row pay for an unrelated expensive join — proposal.yaml:18
  Fix: omit it by default and expose `?include=billing_profile` with a documented cap.

### Gates: Boring ✗ · Compatibility N/A (greenfield) · Authentication ✗ · Authorization ✗ · Idempotency N/A (read-only input) · Blast radius ✗ · Pagination ✗ · Expensive fields ✗ · No implementation leakage ? (unverified: response mechanics not in excerpt)
```

The named export resource is justified by genuinely long-running product work. Do not copy this async shape onto an ordinary read merely because the backend happens to use a job internally.

## Existing HTTP RPC route: do not review for REST purity

Context: this is an existing public API whose other routes use the same `family.method` convention.

Input excerpt (line-numbered `routes.ts`):

```text
17  router.post("/api/chat.postMessage", retryable(handler))
18  handler.idempotency = false
```

```text
## API review: chat post RPC
Scope: public · existing

### Incident risk
- The wrapper retries an action-creating request without deduplication — routes.ts:17-18
  Fix: accept an idempotency key and replay the stored result; do not retry ambiguous
  failures until that contract exists.

### Gates: Boring ✓ · Compatibility N/A (no contract change shown) · Authentication ? (unverified: not in excerpt) · Authorization ? (unverified: not in excerpt) · Idempotency ✗ · Blast radius ? (unverified: limits not in excerpt) · Pagination N/A (not a collection) · Expensive fields ? (unverified: response not in excerpt) · No implementation leakage ? (unverified: response mechanics not in excerpt)
```

`/api/chat.postMessage` is not a finding when `family.method` is the established, predictable convention. Renaming it to look RESTful would create a compatibility break without reducing incident risk.

## Evidence boundary

If published documentation does not guarantee deduplication, conclude only that consumers cannot safely rely on deduplication. Do not claim the backend lacks an undocumented mechanism. For external source code, link to an immutable commit and symbol or line range rather than a moving default branch.

---
name: old-coder-api
description: Design, change, or review an HTTP/JSON API surface — endpoints, request/response shapes, authentication and authorization, pagination, idempotency, rate limits, versioning, and deprecations. Use when adding or modifying an HTTP endpoint, reviewing an OpenAPI spec or HTTP route diff, or deciding whether an HTTP API change breaks consumers. Do not use as a protocol-compatibility checklist for gRPC/protobuf, GraphQL, WebSockets, or other non-HTTP/JSON interfaces.
---

# old-coder-api

Inspired by Sean Goedecke, *Everything I know about good API design* (2025-08-24).

This skill covers HTTP/JSON contract and operability concerns. Its compatibility rules assume JSON consumers. For gRPC/protobuf, GraphQL, WebSockets, or another protocol, apply the transport-independent principles only alongside that protocol's own compatibility rules. This is not a substitute for a full application-security review.

**Good APIs are boring.** For the people who build them, an API is a product. For the people who use them, it is a tool in the way of something else. Every minute a consumer spends thinking about your API instead of their goal is waste. An interesting API is a bad API — or would be a better one if it were less interesting.

Two failure modes an agent falls into by default, and this skill exists to stop both:

1. **Inventing.** Producing a clever, bespoke interface where the boring conventional one would do.
2. **Breaking.** Renaming, restructuring, or tightening a field because it reads better now — and silently breaking every downstream caller.

**Composition with `old-coder`:** when both skills apply, this skill owns the
HTTP/JSON contract while `old-coder` owns workflow order, SPEC approval, the
gauntlet, and EVIDENCE. Run Step 0 and the gates before SPEC approval; put the
surviving API constraints and risks into SPEC and verify them through the
gauntlet. For review-only work with no implementation, use this skill's review
format without manufacturing a development loop.

## Step 0 — establish scope before designing anything

Answer these three, out loud, before writing a route:

| Question | Why it changes the work |
|---|---|
| **Public or internal?** Can you ship code for every consumer? | Internal: breaking changes are affordable, complex authentication is fine, non-engineer ergonomics don't matter. Public: none of that holds. |
| **Existing surface or greenfield?** | Existing → run `references/breaking-changes.md` **first**; compatibility outranks every improvement below. |
| **Does the product's resource model support this API?** | API design tracks the product's basic resources. If the resources are awkward (state machines with no name, records that only exist inside a job, parent/child relations that aren't modeled), the API will be awkward no matter how carefully you design it. Say so instead of papering over it. |

**Honesty rule for step 0:** when the ugliness comes from the underlying model, name it and propose the model fix as the real option. A background-job-polling interface bolted onto a read that *should* be a read is how the worst APIs happen — technical constraints that the UI hides get laid bare in the API, forcing consumers to understand far more of your system than they should have to.

## The gates

Run every gate. Use **✓** only for a verified pass, **✗ + concrete fix** for a verified failure, **N/A + reason** only when the gate truly does not apply, and **? + reason** when it remains unverified. Never skip silently.

### 1. Boring
A competent consumer should be able to guess this endpoint before reading any docs.
- Resources are the product's nouns (`/issues`, `/projects`, `/users`), plural, stable.
- Standard verbs and status codes, following the established convention of this API. Use `400` for a general client error; use `422` only when the content type and syntax are valid but the contained instructions cannot be processed. Use `404` for missing and `429` for rate-limited.
- Standard field names: `id`, `created_at`, `next_page`, `url`. Match the names the rest of *this* API already uses — internal consistency beats external convention when they conflict.
- REST + JSON unless there's a reason. An established, internally consistent HTTP RPC surface can also be boring; do not rename it to resource paths for REST purity. Don't relitigate HATEOAS or JSON-vs-anything; it isn't important.
- **Anything surprising needs a written justification line.** If you can't write one, make it boring.

### 2. Don't break userspace
Applies only to changes on an existing surface. Full matrix in `references/breaking-changes.md`.
- Additive is fine: new endpoints, new optional params, **new response fields**. Consumers are expected to ignore unknown fields.
- Removing a field, renaming it, changing its type, moving it (`user.address` → `user.details.address`), narrowing an enum, or tightening validation is a break. Don't, even if it's neater. The HTTP `referer` header is a misspelling and it is still there.
- If a break is genuinely unavoidable: versioning, as a **last resort** — see the reference.

### 3. Authentication: make the simplest safe path easy
Many server-to-server integrations start life as a `curl` or a 20-line script. For developer-facing server-to-server APIs, default to simple, scoped, revocable API keys.
- Use OAuth or another short-lived or sender-constrained flow instead for browser/mobile clients, user-delegated access, high-sensitivity data, or environments where policy requires it. Do not ship long-lived bearer credentials into those clients.
- For every credential type, define scope, rotation, revocation, secure transport, and a way to identify or disable the credential during an incident.
- N/A for internal credential ergonomics: use the mechanism the infrastructure already provides (mTLS, workload identity, service tokens), while still verifying its operational controls.

### 4. Authorization: enforce who may do what to which resource
Authentication identifies a caller; it does not authorize an action. For every endpoint, identify the actor, action, resource, and tenant boundary.
- Enforce authorization server-side on the resolved resource. Do not trust a caller-supplied `tenant_id`, owner ID, role, or scope without checking it against the authenticated principal.
- Apply the same checks to list, search, bulk, export, nested-resource, and indirect lookup paths; filtering after fetching is not an authorization boundary.
- N/A only for intentionally anonymous public operations, with a one-line reason. For security-sensitive changes, require a dedicated security review in addition to these API gates.

### 5. Idempotency on anything that takes action
A `500` or a timeout tells the caller nothing about whether the action happened. Without an idempotency key, the caller must choose between a lost operation and a duplicate one.
- Every operation that is not already idempotent and creates, triggers, or applies a relative change accepts an idempotency key (header or param); repeat keys return the original result instead of acting twice.
- Keep it **optional for low-stakes operations** where an occasional duplicate is cheaper than added adoption friction.
- When a duplicate is unacceptable — payments, transfers, medication, irreversible external side effects — require an idempotency key or an intrinsic unique operation ID, and enforce deduplication atomically with the effect.
- Not needed for reads (harmless) or `DELETE /comments/32` (the ID *is* the key — the retry just 404s). Exception: non-ID-scoped operations like "delete the most recent".
- Storage recipe in `references/patterns.md`.

### 6. Blast radius, rate limits, killswitch
UI users are limited by the speed of their hands. **Anything you expose via API is called at the speed of code**, forever, in a loop, by someone who read no docs.
- Before shipping: write down what one caller in a tight `while true` loop costs you. Fan-outs, `/index` endpoints, bulk imports, and anything doing per-record work in a request are the dangerous ones.
- Rate limit everything, with **tighter limits on expensive operations**.
- Return `X-RateLimit-Remaining` and `Retry-After` so well-behaved clients can back off — that metadata is what lets you set stricter limits than you otherwise could.
- Keep a per-consumer killswitch. You will need it during an incident caused by an integration you never imagined.

### 7. Pagination
- Any collection that could plausibly grow large: **cursor-based**, always. `WHERE id > :cursor ORDER BY id LIMIT :n` stays fast at record one million; `OFFSET` gets slower every page and the migration away from it later is expensive.
- Bounded-forever collections (a user's API keys, a project's 5 environments): page/offset is fine.
- Never return an unbounded list. Always include `next_page` (URL or cursor) so consumers don't compute it.

### 8. Expensive fields are optional and off by default
If a field needs an extra service call, a join over a big table, or a computation, don't put it in the default response.
- Gate it behind `?include=subscription` / an `includes[]` array; keep the default response cheap and **constant-cost**.
- This is the useful 20% of the GraphQL idea without the cost.
- **Don't propose GraphQL** unless the user asks or the codebase is already GraphQL: high barrier for non-engineers, arbitrary client-crafted queries complicate caching and multiply edge cases, and the backend is fiddlier. It's a last resort, not a default.

### 9. No implementation leakage
Read the response as a stranger. Does using it correctly require knowing how you store things?
- Leaks: `next_comment_id` chains the client must walk; a `POST /fetch_job` + poll dance for what should be a `GET`; internal enum values; internal table IDs; pagination whose page size depends on your shard layout.
- Either hide it behind a boring interface, or state the debt explicitly in the PR — don't let it slip into a public contract unremarked.

## Deliberately not gates

Guard against over-design as hard as under-design:

- **Don't build versioning machinery up front.** A `/v1/` prefix is itself a public product choice, not a free placeholder. Adopt path or header versioning only when the product's compatibility policy calls for it; do not build multi-version negotiation before a second version exists.
- **Don't add `includes` or cursors to internal endpoints with one caller and a bounded result set.** The Pagination and Expensive fields gates are about potentially large or expensive responses. For Idempotency, caller count does not remove retry risk: omit it only when the operation is already idempotent or duplicate effects are explicitly acceptable.
- **Don't rewrite a working API to be prettier.** Prettiness is not worth a compatibility break, and it isn't worth the review time either.
- **Remember API quality is marginal.** If the product is valuable, people integrate with a terrible API (Facebook, Jira). If it isn't, a beautiful API won't save it. API quality decides between two roughly equivalent products; having *no* API at all is the real defect. So: apply these gates, don't gold-plate past them.

## Review output format

When reviewing rather than writing, report only findings that survive verification and skip taste. For repository code, specs, and diffs, cite `file:line`. For published contracts outside the repository, cite a stable URL and exact section; source-code evidence must use an immutable commit permalink, not a moving branch. A missing public guarantee means consumers cannot rely on the behavior; it does **not** prove that the backend lacks an undocumented implementation. Give a gate `✓` only when the reviewed evidence supports it. When repository context is available, inspect beyond the diff instead of treating silence as a pass. If the input is intentionally limited and further evidence is unavailable, use `? (unverified: <reason>)`; reserve `N/A` for a gate that truly does not apply. Gate summaries evaluate the artifact under review, not the hypothetical state after suggested fixes. Order: breaks first, security boundaries second, incidents third, ergonomics last.

```
## API review: <surface>
Scope: public|internal · greenfield|existing

### Breaking changes (blocking)
- <field/endpoint> — <what breaks for a consumer doing X> — file:line
  Fix: <additive alternative>

### Security boundary
- <authentication/authorization finding> — <credential or unauthorized action/resource> — file:line

### Incident risk
- <idempotency/blast-radius finding> — <the loop or retry that hurts> — file:line

### Ergonomics
- <boring/pagination/field-cost/implementation-leak finding> — file:line

### Gates: Boring <status> · Compatibility <status> · Authentication <status> · Authorization <status> · Idempotency <status> · Blast radius <status> · Pagination <status> · Expensive fields <status> · No implementation leakage <status>
```

If nothing survives, say so plainly — an empty review is a valid result.

## References

- `references/breaking-changes.md` — compatibility matrix, versioning playbook, deprecation sequence. **Read before changing any existing endpoint.**
- `references/patterns.md` — implementation recipes: idempotency keys, cursor pagination, rate-limit headers, `includes`.
- `references/examples.md` — three compact, local examples: an existing route/spec diff, a greenfield proposal, and an established HTTP RPC route. Read only when a concrete calibration example is useful.

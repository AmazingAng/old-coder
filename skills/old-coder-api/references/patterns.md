# Implementation recipes

Boring, known-good shapes. Prefer whatever this codebase already does over anything here; consistency inside one API beats matching an external example.

## Idempotency keys

**Contract**

```
POST /v1/comments
Idempotency-Key: 8f1e...  (client-generated UUID, optional)
```

- First request with a given key: perform the action, store `key → (status, response body)`.
- Repeat with the same key: return the **stored response**, don't act again. Same status code as the original.
- Same key, *different* request body: reject it using this API's established `400`/`409`/`422` error convention. Silently returning the first response would hide a client bug.
- In flight when the retry arrives: `409`, telling the client to retry shortly. (Take a lock on the key at the start of processing.)

**Storage**

A key/value store (Redis) with the idempotency key as the key is enough for most low-stakes cases. Scope by user (`idem:{user_id}:{key}`) — UUIDs are unique enough that you don't strictly need to, but you may as well. Set expiry from a documented retry window; a few hours may be enough for low-stakes immediate retries, but it is not a universal default.

Caveat worth stating when it matters: Redis and your database can't be updated atomically together, so under a crash between the two you can still double-act. For payments and other high-risk paths, store the key in the same transaction as the effect — e.g. a unique column/row in the same database. For everything else, bolting Redis idempotency onto a non-idempotent API is much better than nothing.

**Where it's needed**

| Operation | Key needed? |
|---|---|
| `GET` anything | No — double reads are harmless |
| `DELETE /comments/32` | No — the resource ID *is* the key; retries just `404` |
| `DELETE` "the most recent X" | **Yes** — not ID-scoped |
| `POST /comments` (create) | Yes |
| `POST /transfers`, `/charges`, irreversible side effects | **Required**, unless an intrinsic unique operation ID provides equivalent atomic deduplication |
| `PUT /users/32` (full replace) | Usually not — replacing with the same body twice is the same end state. Still yes if it fires side effects (emails, webhooks, audit rows). |
| `PATCH` with relative semantics (`increment: 1`) | Yes |

Keep the key **optional for low-stakes operations**. Document it and default it in your own SDKs. For duplicate-intolerable operations, require it (or an equivalent unique operation ID) rather than accepting an unsafe request.

## Cursor pagination

**Request/response**

```
GET /v1/tickets?limit=50&cursor=eyJpZCI6MzJ9

{
  "data": [ ... ],
  "next_page": "/v1/tickets?limit=50&cursor=eyJpZCI6ODJ9",
  "has_more": true
}
```

**Query**

```sql
SELECT * FROM tickets
WHERE account_id = :account AND id > :cursor
ORDER BY id
LIMIT :limit
```

Fast at any depth because the index locates the cursor row directly. `OFFSET 200000` makes the database count through 200,000 rows every time, so each page is slower than the last.

**Rules**
- Sort key must be **unique and stable**. `ORDER BY created_at` alone breaks on ties — use `(created_at, id)` and encode both in the cursor.
- Opaque cursors (base64 of a small JSON blob) let you change the sort key later without breaking consumers. A raw `cursor=32` is a contract you'll regret.
- Cap `limit` server-side. Document the cap and the default; changing the default later is a breaking change.
- Always emit `next_page` (or `null`) so consumers never construct it. That's also what lets you switch strategies later.
- Ending condition: `has_more: false` / `next_page: null`. Don't make clients infer it from a short page — a short page is legal mid-collection when you filter after fetching.

Offset pagination is fine for collections that are bounded forever (a user's API keys, a project's environments). Anything user-generated and unbounded: cursor from day one, because retrofitting it later is a breaking change you'll be forced into at the worst moment.

## Rate limiting

**Response headers on every rate-limited endpoint**

```
X-RateLimit-Limit: 700
X-RateLimit-Remaining: 412
X-RateLimit-Reset: 1755300000     # epoch seconds
Retry-After: 32                   # seconds; on 429 responses
```

Status `429` when exceeded. (Standardized `RateLimit-*` headers exist; if your ecosystem already uses `X-`-prefixed ones, stay consistent with it.)

**Tiering**

Set limits by cost, not by uniform policy:

| Class | Example | Relative limit |
|---|---|---|
| Cheap read by ID | `GET /tickets/32` | High |
| List / search | `GET /tickets?query=` | Medium |
| Write | `POST /tickets` | Medium |
| Fan-out, bulk, export, anything doing per-record work | `POST /apps/:id/notify_all` | Low, and consider making it async with a job resource |

**Killswitch.** A per-consumer (account, API key, app) disable that an on-call engineer can flip without a deploy. Incidents caused by third-party integrations are routine — polling an `/index` endpoint with no delay, create/delete loops, imports with no backoff — and you need pressure relief that doesn't require the customer's cooperation.

## Optional / expensive fields

```
GET /v1/users/32                              → cheap, constant-cost fields only
GET /v1/users/32?include=subscription,posts   → adds the expensive ones
```

- One `include` param taking a comma-separated list (or `includes[]`) scales better than a boolean per field.
- Validate the values and return the API's established client-error status (`400` or `422`) on unknown ones — a typo that silently returns less data is a bad debugging afternoon.
- Cap what can be combined. `include=posts` on a user with 100k posts is a fan-out; either paginate the sub-resource or expose it as its own endpoint.
- The default response should be **constant-cost**: no N+1, no cross-service call, no unbounded array. That's the invariant this pattern is protecting.

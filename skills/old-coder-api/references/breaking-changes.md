# Breaking changes, versioning, deprecation

Read this before modifying any HTTP/JSON endpoint that already has consumers. These rules do not replace protocol-specific compatibility guidance for protobuf, GraphQL, or other representations.

> As the maintainer of an API you have something like a sacred duty to your downstream consumers. One careless maintainer far enough upstream breaks hundreds of pieces of software. **WE DO NOT BREAK USERSPACE.**

## Compatibility matrix

Assume a consumer that parses your JSON into a typed struct, ignores unknown fields, and was written two years ago by someone who has left the company.

| Change | Safe? | Notes |
|---|---|---|
| New endpoint | ✅ | |
| New **optional** request param | ✅ | Default must reproduce the old behavior exactly. |
| New response field | ✅ | Consumers are expected to ignore unknown fields. A consumer that explodes on extra fields is being irresponsible — but check for known strict clients before assuming. |
| New optional response field inside an existing object | ✅ | |
| Remove a response field | ❌ | Even if it's always `null`. Even if "nobody uses it" — check logs before believing that. |
| Rename a field | ❌ | This is remove + add. If truly needed: add the new name, keep the old one populated, forever. |
| Move a field (`user.address` → `user.details.address`) | ❌ | Same as rename. |
| Change a field's type (`"3"` → `3`, scalar → array, int → string ID) | ❌ | Silently corrupts typed consumers. |
| Change a field's semantics under the same name/type | ❌ | The worst kind: no error, wrong behavior, undetectable in tests. |
| Add a value to a response enum | ⚠️ | Breaks exhaustive-match consumers. Safe only if the enum was documented as open-ended from day one. |
| Remove a value from a request enum | ❌ | |
| **Tighten** validation (new required param, stricter regex, lower max) | ❌ | Requests that worked yesterday now fail with a client error. |
| **Loosen** validation | ✅ | |
| Make a required param optional | ✅ | |
| Change a default value | ❌ | It changes behavior for every caller who omitted the param. |
| Change default page size | ❌ | Callers hardcode the count or the loop bound. |
| Change a status code (`200`→`201`, `404`→`422`) | ❌ | Callers branch on it. |
| Change error response *shape* | ❌ | Callers parse it. Adding a new field to it is fine. |
| Change ordering of a list without a documented sort | ⚠️ | Formally allowed, practically breaks pagination and diff-based consumers. Treat as breaking. |
| New rate limit / tighter rate limit | ⚠️ | Breaks heavy callers at runtime, not at compile time. Announce, measure top callers first, roll out gradually. |
| Fix a bug consumers may have worked around | ⚠️ | Real judgment call. Measure how many callers depend on the buggy behavior. |

Rule of thumb: **additive is safe, subtractive and restrictive are not.** When unsure, it's breaking.

## Before claiming "nobody uses this"

Don't assert it — check, and cite what you checked:
1. Access logs / analytics per endpoint and, if available, per field.
2. First-party callers in the monorepo or sibling repos (grep the path string).
3. SDKs, docs, examples, support macros, and anything a customer copy-pasted from a blog post.

If you cannot check, you cannot claim it. Say "unverified" in the PR.

## Versioning — a necessary evil, and a last resort

It is honestly hard to find a case where an API genuinely *needs* a breaking change. When the technical value is high enough that you bite the bullet anyway, versioning means: **serve the old and the new version at the same time.**

Two shapes:
- **URL path** — `/v1/chat/completions` → `/v2/chat/completions`. Simplest, most visible, easiest for consumers to reason about.
- **Header / account default** — Stripe's model: a version header, plus a per-account default set in the UI. Consumers upgrade at their own pace.

Costs to state plainly before proposing it:
- 30 endpoints × a new version = 30 more surfaces to test, debug, document, and support.
- A translation layer (serialize/deserialize per version, one shared core) keeps the codebase from doubling — but that abstraction always leaks. Some version differences require conditional logic down in the core, and Stripe engineers have said so publicly.
- Docs and search become confusing: users land on the wrong version's page.
- Migration takes **months to years**, with banners, emails, response headers — and you will *still* have angry users on removal day.

So: exhaust the additive options first. In order —
1. New optional param that opts into the new behavior.
2. New field alongside the old one, both populated.
3. New endpoint (`/users/:id/details`) beside the old one.
4. New version. Only here.

## Deprecation sequence

When something must eventually go:

1. **Ship the replacement first.** Never announce a removal before the alternative is live and documented.
2. **Announce**: docs banner, changelog, direct email to identified callers, and a `Deprecation` / `Sunset` header on responses to the old surface.
3. **Measure.** Track calls to the deprecated surface by consumer. This is the number that decides the date, not the calendar.
4. **Wait.** Months, not weeks. Public and widely used: a year is not excessive.
5. **Brownout** (optional, effective): return errors for the old surface for a few scheduled hours, announced in advance. Wakes up the callers that ignored every email.
6. **Remove** — and expect complaints anyway. At that point you've done what you can.

For internal APIs, compress this hard: you can grep every caller and ship the fix yourself. Do that instead of a deprecation program.

## Internal APIs

The relaxations, stated precisely — internal means *you can ship code for every consumer*:
- Breaking changes are affordable: change the callers in the same PR, or in a two-step ship (add new → migrate callers → remove old).
- Auth can be as complex as your infra wants.
- Consumers are professional engineers; ergonomics for non-engineers doesn't apply.

What does **not** relax: internal APIs are still a top source of incidents, and key operations still need idempotency. A retrying internal client double-charging something is exactly as bad as an external one doing it.

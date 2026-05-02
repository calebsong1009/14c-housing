# Catalog Templates

This directory defines the Pydantic schema (`templates.py`) for two catalogs that the compliance engine consumes:

- **Trigger catalog** — predicates over household data that, when satisfied, emit requirement instances.
- **DocumentSetRequirement catalog** — descriptions of which documents satisfy a requirement, expressed as a recursive `document_spec` (`document` leaf, `all_of`, `one_of`).

The schema is the contract. The catalog *content* — the actual list of triggers and requirements for the Danvers Maple Square form — is built by `build_catalogs.py` and serialized to `trigger_catalog.json` + `req_catalog.json` next to it. Re-run the script any time the catalog changes; both JSON files are regenerated deterministically.

## Engine flow

1. Load household data (shape: `eval_set_template_jsons/family_template.json`) and the uploaded document bundle.
2. For each `Trigger`, evaluate `activation` against household data.
3. If fired, emit one or more `RequirementInstance`s based on `instance_scope` (see below).
4. For each instance, recursively evaluate its `document_spec` against the bundle. A `document` leaf is satisfied iff a matching document exists (filtered by `applies_to_member` when the role is `member`); `all_of` requires every child; `one_of` requires at least one.
5. Pass = all instances satisfied. Fail = list of unsatisfied instances, each carrying `triggered_by` + (looked-up) `source_reference` for the audit trail.

## Input contract

The engine consumes household data shaped like `eval_set_template_jsons/family_template.json`. Synthetic data generators **must** conform to the following format conventions, because the predicate engine does no coercion:

- Monetary amounts are JSON numbers (not strings, not "$1,200").
- Dates are ISO-8601 strings (`"YYYY-MM-DD"`). With this format, `greater_than` / `less_than` over strings yields correct chronological ordering.
- Member ages are integers.
- Booleans are real JSON booleans, not `"yes"` / `"no"` strings.
- Free-text classification fields (e.g. `applicant_other_income_type`) are strings; predicates over them rely on `contains` / `equals` and exact wording.

If the parser ever changes upstream, normalize before handing data to the engine — do not push coercion responsibility into the predicate evaluator.

## Self-attestation model

The Danvers application (PDF pages 18–20, "Required Personal Identification and Income Verification Documents") is itself a self-attestation checklist: the applicant **initials** each item that applies. The `eligibility_checklist.*` booleans in `family_template.json` mirror that section exactly. So:

- `eligibility_checklist.*` is **engine input**, not engine output. It is the form's authoritative signal for items the form does not capture as structured fields.
- The engine validates that the **documents match the checklist**, not that the checklist is honest. A dishonest checklist is out of scope.

### Triggers keyed off the checklist (self-attested)

For most asset/income items the checklist is the primary (or only) signal. Each listed key activates as `eligibility_checklist.<key> == true`:

`section_8_or_housing_voucher`, `proof_of_local_preference`, `special_accommodation_documentation`, `pay_stubs`, `benefit_letter`, `child_support_alimony`, `self_employment`, `w2_1099r`, `interest_dividends_income`, `checking_account_statements`, `prepaid_debit_card_statements`, `digital_wallet_statements`, `savings_account_statements`, `revocable_trusts`, `equity_rental_or_capital_investments`, `investment_accounts`, `retirement_accounts`, `life_insurance_cash_value`, `personal_property_investment`, `lump_sum_one_time_receipts`, `student_status_proof`, `proof_of_pregnancy`, `divorce_or_separation`.

### Universal triggers (every applicant)

Some documents are required of every applicant, with no conditional logic — Affidavit & Disclosure, signed Application Tips, Release of Information, and the federal tax return (a 2024 return *or* IRS non-filing letter is required of everyone). These triggers use `household.total_size greater_than 0` as an "always" predicate. Identification is also universal but uses `instance_scope = "per_member"` with a `name exists` tautology so it fans out one instance per household member.

### Triggers that additionally key off structured fields (sanity overlay)

The catalog *may* encode redundant structural triggers as a sanity check. Both paths emit the same `requirement_id`; the engine dedupes by instance label. Examples currently in the catalog:

| Structured field | Implied requirement |
|---|---|
| `personal_information.section_8_or_housing_voucher == true` | voucher copy |
| `personal_information.requires_wheelchair_accessible_unit == true` or `requires_special_accommodation == true` | doctor's letter |
| `employment.date_of_hire exists` | pay stubs + employment offer letter (the form's "last 12 months" condition is not enforced — the DSL has no date arithmetic) |
| `assets.<category> > 0` | statement for that asset category |

### MVP gaps in the self-attestation model

A few PDF-mandated items have no signal in the application or checklist and are deliberately omitted from the MVP catalog:

- **Separation letter** (PDF p.18 item 5 NOTE): required if the applicant left an employer in the last 12 months. There is no application field or checklist item for "previous employer". Skipped.
- **Unemployment / DOR verification / disability / workers' comp / severance** (PDF p.18 item 5): the form lumps these under pay stubs. The application has no field distinguishing them. Treated as covered by the pay-stub trigger.
- **Custody & Child Support Affidavit (per minor)**: PDF p.25 requires it only for minors not living with both biological/adoptive parents. There is no signal for the parental relationship in `family_template.json`. The catalog over-fires conservatively: any `member.age < 18` when `eligibility_checklist.child_support_alimony == true`.

## Instance scopes

`Trigger.instance_scope` controls how a fired trigger fans out into instances:

- `"household"` — one instance, `applies_to_role = "household"`.
- `"applicant"` — one instance, `applies_to_role = "applicant"`. The applicant lives in `personal_information` / `financials.applicant_*` / `employment` — outside `household.members[]` — so it is a first-class scope.
- `"co_applicant"` — one instance, `applies_to_role = "co_applicant"`. Same reasoning as applicant.
- `"per_member"` — one instance per member of `household.members[]` for whom `per_member_scope` evaluates true. `applies_to_role = "member"` and `applies_to_member` is the engine-minted hash.

Validators in `templates.py` enforce: `per_member_scope` is required iff `instance_scope == "per_member"`, and forbidden otherwise.

## Per-member scope semantics

`Predicate.field` inside a `per_member_scope` is interpreted **relative to the member object** (`age`, `relationship`, `name`), not the household root. To filter on cross-cutting household state, gate on `Trigger.activation` (which is evaluated against the household root) and use a simple member predicate inside `per_member_scope`. The two layers compose: activation gates whether the trigger fires at all; per_member_scope picks which members get instances when it does.

For "every member" semantics, use a tautology like `Predicate(field="name", operator="exists")` — the validator in `templates.py` requires `per_member_scope` to be non-None whenever `instance_scope == "per_member"`, so a no-op predicate is the right way to express "match all members". This is how `trig_household_member_id` fans the universal ID requirement out per member.

## Member ID minting

The input schema gives no stable member identifier. The engine mints one at load time. Recommended scheme:

```
sha256(f"{name}|{relationship}|{age}".encode()).hexdigest()[:8]
```

The same hash is used both on `RequirementInstance.applies_to_member` and on document-bundle metadata (`applies_to_member` field per uploaded document). Document leaf evaluation filters the bundle by this hash when the instance's role is `member`.

**Known MVP limitation:** if the applicant edits a member's name/age, the hash changes and previously-uploaded documents orphan. Acceptable for now — flag if encountered.

## Audit trail

`RequirementInstance` carries `triggered_by` (list of trigger IDs) but **not** a copy of `source_reference`. Audit consumers resolve the source reference by looking up each `trigger_id` in the trigger catalog. This avoids duplication; the engine's catalog loader is the single source of truth.

## MVP non-goals

The DSL deliberately does not enforce any of the following. They are all candidates for a future iteration but are out of scope right now:

- Document recency / coverage windows / "5 consecutive paystubs" / minimum counts. `DocumentLeaf.notes` carries this as free text and is **advisory only** — the engine checks document presence, not the constraints in the note.
- Date arithmetic in predicates. The DSL has `greater_than` / `less_than` over ISO-8601 strings, but no "within last N months". Triggers like `employment_offer_letter` over-fire on any non-null `employment.date_of_hire`.
- Exclusion / forbidden combinators on `DocumentSpec`. Only `all_of` and `one_of` exist.
- Validation that the user's eligibility-checklist self-attestation is truthful. The engine validates that documents match the checklist, full stop.

`build_catalogs.py` does perform a cross-check that every `Trigger.emits_requirements` references a real `requirement_id` — at build time, not at engine load. The README previously called this out as a non-goal; it has graduated into a build-time guardrail.

## Files

- `templates.py` — Pydantic models for `Trigger`, `DocumentSetRequirement`, `RequirementInstance`, and the document/condition DSLs.
- `build_catalogs.py` — one-shot builder. Constructs every `Trigger` and `DocumentSetRequirement` as Pydantic objects (so all model validators run at build time), cross-checks `emits_requirements` against the requirement catalog, and writes the JSON outputs. Run as `python3 catalog_templates/build_catalogs.py`.
- `req_catalog.json` — generated. List of `DocumentSetRequirement` JSON.
- `trigger_catalog.json` — generated. List of `Trigger` JSON.
- `handcoded_trigger_catalog.json` / `.py` — original hand-authored thinking document and notes file. Kept for reference; not consumed by anything.
- `../eval_set_template_jsons/family_template.json` — input schema (read-only reference).
- `../eval_set_template_jsons/bundle_template_total_options.json` — universe of available `document_type` strings; every `DocumentLeaf.document_type` in the catalog must be a member of this set.
- `../Danvers Maple Sq FCFS Application 2026.pdf` — the form whose semantics this catalog encodes (read-only reference).

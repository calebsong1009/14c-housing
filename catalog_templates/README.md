# Catalog Templates

This directory defines the Pydantic schema (`templates.py`) for two catalogs that the compliance engine consumes:

- **Trigger catalog** — predicates over household data that, when satisfied, emit requirement instances.
- **DocumentSetRequirement catalog** — descriptions of which documents satisfy a requirement, expressed as a recursive `document_spec` (`document` leaf, `all_of`, `one_of`).

The schema is the contract. The catalog *content* (the actual list of triggers and requirements for a given form) lives elsewhere and is authored against this schema.

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

These items have no other structured signal in the input — the checklist is the only source:

`section_8_or_housing_voucher`, `proof_of_local_preference`, `special_accommodation_documentation`, `pay_stubs`, `employment_offer_letter`, `separation_letter`, `benefit_letter`, `child_support_alimony`, `self_employment`, `federal_tax_returns_2024`, `irs_non_filing_verification`, `w2_1099r`, `interest_dividends_income`, `checking_account_statements`, `prepaid_debit_card_statements`, `digital_wallet_statements`, `savings_account_statements`, `revocable_trusts`, `equity_rental_or_capital_investments`, `investment_accounts`, `retirement_accounts`, `life_insurance_cash_value`, `personal_property_investment`, `lump_sum_one_time_receipts`, `student_status_proof`, `proof_of_pregnancy`, `divorce_or_separation`, `household_member_identification`.

### Triggers that can additionally key off structured fields (sanity overlay)

The catalog *may* encode redundant structural triggers as a sanity check. Examples:

| Structured field | Implied requirement |
|---|---|
| `personal_information.section_8_or_housing_voucher == true` | voucher copy |
| `personal_information.requires_wheelchair_accessible_unit == true` or `requires_special_accommodation == true` | doctor's letter |
| `personal_information.ever_owned_home == true` | home-sold-date evidence |
| `employment.date_of_hire` within last 12 months | employment offer letter |
| `assets.<category> > 0` | statement for that asset category |
| Any `household.members[i].age >= 18` | per-adult income/asset docs |

Nothing in the DSL prevents both kinds of triggers from coexisting; an instance satisfied by either path passes.

## Instance scopes

`Trigger.instance_scope` controls how a fired trigger fans out into instances:

- `"household"` — one instance, `applies_to_role = "household"`.
- `"applicant"` — one instance, `applies_to_role = "applicant"`. The applicant lives in `personal_information` / `financials.applicant_*` / `employment` — outside `household.members[]` — so it is a first-class scope.
- `"co_applicant"` — one instance, `applies_to_role = "co_applicant"`. Same reasoning as applicant.
- `"per_member"` — one instance per member of `household.members[]` for whom `per_member_scope` evaluates true. `applies_to_role = "member"` and `applies_to_member` is the engine-minted hash.

Validators in `templates.py` enforce: `per_member_scope` is required iff `instance_scope == "per_member"`, and forbidden otherwise.

## Per-member scope semantics

`Predicate.field` inside a `per_member_scope` is interpreted **relative to the member object** (`age`, `relationship`, `name`), not the household root. To filter on cross-cutting household state, gate on `Trigger.activation` (which is evaluated against the household root) and use a simple member predicate inside `per_member_scope`. The two layers compose: activation gates whether the trigger fires at all; per_member_scope picks which members get instances when it does.

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
- Cross-validation of `Trigger.emits_requirements` against the requirement catalog at load time. The compliance engine will fail naturally when it tries to instantiate a missing requirement; that is sufficient for MVP.
- Exclusion / forbidden combinators on `DocumentSpec`. Only `all_of` and `one_of` exist.
- Validation that the user's eligibility-checklist self-attestation is truthful. The engine validates that documents match the checklist, full stop.

## Files

- `templates.py` — Pydantic models for `Trigger`, `DocumentSetRequirement`, `RequirementInstance`, and the document/condition DSLs.
- `../eval_set_template_jsons/family_template.json` — input schema (read-only reference).
- `../Danvers Maple Sq FCFS Application 2026.pdf` — the form whose semantics this catalog encodes (read-only reference).

# Feedback Agent

End-of-pipeline component. Takes a failed compliance result and human feedback explaining what was wrong, then uses an LLM to reason about the minimal fix and outputs updated trigger and requirement catalogs.

---

## Where this fits in the pipeline

```
P1: Catalog Authoring
        ↓
P2: Compliance Engine  ──→  compliance trace (what fired, what failed)
        ↓                          ↓
P3: Eval / Scoring         Feedback Agent  ←── human evaluator explains what was wrong
                                   ↓
                         updated trigger catalog
                         updated req catalog
```

---

## Inputs

| Input | Type | Description |
|-------|------|-------------|
| `trigger_catalog` | `list[dict]` | Full trigger catalog — every trigger in the system |
| `req_catalog` | `list[dict]` | Full requirement catalog — every document set requirement |
| `bundle` | `dict` | Document bundle the applicant submitted |
| `family` | `dict` | Household / application data |
| `compliance_trace` | `dict` | Output of `run_compliance_trace()` — which triggers fired, which requirements were emitted, which failed and what docs were missing |
| `human_feedback` | `str` | Plain-English explanation of what was wrong with the compliance decision |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `updated_triggers` | `list[dict]` | Full trigger catalog with the fix applied |
| `updated_reqs` | `list[dict]` | Full requirement catalog with the fix applied |
| `analysis` | `str` | LLM's explanation of what it changed and why |

---

## Files

### `agent.py`
**The feedback agent itself.**

`run_feedback_agent(trigger_catalog, req_catalog, bundle, family, compliance_trace, human_feedback)` — sends all inputs to Claude (claude-sonnet-4-6) with a system prompt that includes the full catalog DSL schema. The LLM reasons about what needs to change and returns a JSON diff (`trigger_changes`, `req_changes`). The function applies those changes to the catalogs and returns the updated lists.

Also has a CLI entry point:
```bash
python agent.py \
    --triggers  catalogs/trigger_catalog.json \
    --reqs      catalogs/req_catalog.json \
    --bundle    ../usecases/bundle_3.json \
    --family    ../usecases/family_3.json \
    --feedback  "The pay stubs rule only needs 3 stubs not 5" \
    --out-triggers updated_triggers.json \
    --out-reqs     updated_reqs.json
```

**Requires:** `ANTHROPIC_API_KEY` in the environment. Cost is ~2–3 cents per call.

---

### `compliance.py`
**Minimal compliance engine (P2-compatible).**

Two public functions:

`run_compliance(family, bundle, triggers, reqs)` → `(passed: bool, failed_labels: list[str])`
Lightweight pass/fail check. Used in tests to assert before/after.

`run_compliance_trace(family, bundle, triggers, reqs)` → `dict`
Full audit trail. Returns which triggers fired, which requirements were emitted from each, and for each requirement whether it was satisfied and what documents were missing. This is what gets passed to the feedback agent as context for the LLM.

Example trace output:
```json
{
  "passed": false,
  "trigger_trace": [
    {"trigger_id": "trig_pay_stubs", "fired": true, "emitted_requirements": ["req_pay_stubs"]}
  ],
  "requirement_trace": [
    {
      "requirement_id": "req_pay_stubs",
      "instance_label": "req_pay_stubs",
      "triggered_by": ["trig_pay_stubs"],
      "applies_to_member": null,
      "satisfied": false,
      "missing_document_types": ["pay_stub_4.pdf", "pay_stub_5.pdf"]
    }
  ]
}
```

**Origin:** Written for this agent. Not from the repo — the repo has the Pydantic schema (`catalog_templates/templates.py`) but no running engine. This implements the engine logic described in `catalog_templates/README.md`.

---

### `catalogs/trigger_catalog.json`
**Sample trigger catalog — 11 triggers.**

Covers the main eligibility checklist items: household member ID, pay stubs, federal tax returns, W-2/1099-R, Section 8 voucher, local preference, child support, checking/savings accounts, benefit letter, retirement accounts.

Contains **one deliberate bug** for reference: `trig_federal_tax_returns` fires on `employment.date_of_hire exists` instead of the checklist field — the same bug used in Test 2.

**Origin:** Written from scratch. The repo has the schema (`catalog_templates/templates.py`) and the source form (`Danvers Maple Sq FCFS Application 2026.pdf`) but no authored catalog content. P1 is responsible for the real catalog; this is a representative sample for development and testing.

---

### `catalogs/req_catalog.json`
**Sample requirement catalog — 11 requirements.**

One entry per trigger above. Each `document_spec` uses the DSL from `catalog_templates/templates.py` (`document` leaf, `all_of`, `one_of`).

Contains **two deliberate bugs** for reference:
- `req_household_member_id` only accepts `birth_certificate.pdf` (should also accept `driver_license.pdf`, `passport.pdf`) — same bug as Test 3.
- `req_pay_stubs` requires all 5 pay stubs (should require 3) — same bug as Test 1.

**Origin:** Same as above — written from scratch as a representative sample.

---

### `tests/test_feedback_agent.py`
**3 integration tests.**

Each test:
1. Defines a minimal trigger + requirement catalog with one deliberate bug
2. Runs `run_compliance_trace` on a real (family, bundle) pair from the repo — asserts it **fails**
3. Calls `run_feedback_agent` with natural-language feedback describing the bug
4. Runs compliance again on the same pair with the updated catalogs — asserts it **passes**
5. Checks the edit was surgical (only the described item changed)

| Test | Family / Bundle | Bug | Feedback describes | Expected fix |
|------|----------------|-----|--------------------|--------------|
| T1 | `family_3` / `bundle_3` | `req_pay_stubs` requires 5 stubs | Only 3 are required | Shrink `document_spec` from `all_of[5]` to `all_of[3]` |
| T2 | `family_4` / `bundle_4` | `trig_federal_tax_returns` fires on `employment.date_of_hire` exists | Should fire on checklist field | Change trigger `activation` to check `eligibility_checklist.federal_tax_returns_2024.checked` |
| T3 | `family_5` / custom bundle with `driver_license.pdf` | `req_household_member_id` only accepts `birth_certificate.pdf` | Driver's license is valid ID | Widen `document_spec` to `one_of[birth_certificate, driver_license, passport]` |

**Data origin:** `family_3`, `family_4`, `family_5`, `bundle_3`, `bundle_4` are real files from `usecases/` in the repo. The trigger/req catalogs in each test are written inline with deliberate bugs. The bundle for T3 (`BUNDLE_T3`) is custom — no existing bundle had a driver's license without a birth certificate.

---

## Data formats (from `catalog_templates/templates.py`)

### Trigger
```json
{
  "trigger_id": "trig_pay_stubs",
  "description": "...",
  "activation": <Condition>,
  "emits_requirements": ["req_pay_stubs"],
  "instance_scope": "household | applicant | co_applicant | per_member",
  "per_member_scope": null,
  "source_reference": {"document": "...", "section": "..."}
}
```

### DocumentSetRequirement
```json
{
  "requirement_id": "req_pay_stubs",
  "description": "...",
  "document_spec": <DocumentSpec>,
  "source_reference": {"document": "...", "section": "..."}
}
```

### Condition DSL
```json
{"type": "predicate", "field": "eligibility_checklist.pay_stubs.checked", "operator": "equals", "value": true}
{"type": "all",  "children": [<Condition>, ...]}
{"type": "any",  "children": [<Condition>, ...]}
{"type": "not",  "child":    <Condition>}
```

### DocumentSpec DSL
```json
{"type": "document", "document_type": "pay_stub_1.pdf"}
{"type": "all_of",   "children": [<DocumentSpec>, ...]}
{"type": "one_of",   "children": [<DocumentSpec>, ...]}
```

### Family JSON (from `usecases/family_*.json`)
```
personal_information.*, household.{total_size, members[{name, relationship, age}]},
financials.*, assets.*, employment.*, eligibility_checklist.*
```
Each checklist item: `{"checked": bool, "if_applicable": bool, "require": "all"|"any"}`

### Bundle JSON (from `usecases/bundle_*.json`)
```json
{"bundle_id": "bundle_1", "documents": ["birth_certificate.pdf", "pay_stub_1.pdf", ...]}
```

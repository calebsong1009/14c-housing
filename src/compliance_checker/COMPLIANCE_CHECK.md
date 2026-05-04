# compliance_check.py

Evaluates whether a family application and document bundle satisfy all compliance requirements for that family, as determined by the trigger and requirement catalogs.

## Usage

```bash
python compliance_checker/compliance_check.py <family.json> <bundle.json> <trigger_catalog.json> <req_catalog.json>

# write report to a file instead of stdout
python compliance_checker/compliance_check.py <family.json> <bundle.json> <trigger_catalog.json> <req_catalog.json> -o result.json
```

**Example against the sample data:**

```bash
python compliance_checker/compliance_check.py \
    usecases/family_1.json \
    usecases/bundle_1.json \
    catalog_templates/trigger_catalog.json \
    catalog_templates/req_catalog.json \
    -o results/family_1_result.json
```

## Inputs

| Argument | Description |
|---|---|
| `family.json` | Applicant household data (name, income, assets, eligibility checklist) |
| `bundle.json` | List of document filenames submitted by the applicant |
| `trigger_catalog.json` | Rules that decide which requirements apply to a given family |
| `req_catalog.json` | The document specifications each requirement demands |

All four files ship in this repo: family and bundle data live in `usecases/`, catalogs live in `catalog_templates/`.

## How it works

The engine runs in three stages.

### 1. Trigger evaluation

Each trigger in the catalog defines an `activation` condition — a predicate or boolean combination of predicates — evaluated against the family data. If the condition is true, the trigger **fires** and emits one or more requirement IDs.

Examples of what causes a trigger to fire:
- `household.total_size > 0` — always fires (universal documents required of every applicant)
- `eligibility_checklist.pay_stubs == true` — fires when the applicant self-attested to wage income
- `assets.savings > 0` — fires when the family reported a savings balance

### 2. Instance scoping

When a trigger fires, it produces one or more **requirement instances** depending on its `instance_scope`:

- `household` — one instance covering the whole application
- `applicant` / `co_applicant` — one instance for that specific role
- `per_member` — one instance **per household member** who matches the trigger's `per_member_scope` filter (e.g., one ID requirement per person, one custody affidavit per minor)

### 3. Document spec evaluation

Each requirement instance specifies which documents satisfy it via a recursive `document_spec`:

- `document` leaf — the named file must be present in the bundle
- `all_of` — every child spec must be satisfied (AND)
- `one_of` — at least one child spec must be satisfied (OR)

These can nest arbitrarily. For example, the child support requirement is:

```
one_of(
    child_support_none_received.pdf,
    all_of(
        child_support_received.pdf,
        child_support_court_document.pdf,
        divorce_papers.pdf
    )
)
```

This passes if either the "none received" letter is present, or all three of the court documents are present.

## Output

A single JSON object written to stdout (or `-o` path):

```json
{
  "family_id": "family_1",
  "bundle_id": "bundle_1",
  "passed": false,
  "triggers": [
    {
      "trigger_id": "trig_pay_stubs_checklist",
      "description": "Self-attested wage income → require 5 consecutive pay stubs",
      "fired": true,
      "source_reference": {
        "document": "Maple Square FCFS Application 2026",
        "page": 18,
        "section": "Required Documents item 5",
        "quote": null
      },
      "requirement_fulfilled": false,
      "instances": [
        {
          "instance_label": "req_pay_stubs",
          "requirement_id": "req_pay_stubs",
          "applies_to_member": null,
          "fulfilled": false,
          "missing_documents": ["pay_stub_4.pdf", "pay_stub_5.pdf"]
        }
      ]
    }
  ]
}
```

### Field reference

**Top level**

| Field | Type | Description |
|---|---|---|
| `family_id` | string | From the family JSON |
| `bundle_id` | string | From the bundle JSON |
| `passed` | bool | `true` only if every fired trigger's every instance is satisfied |
| `triggers` | array | One entry per trigger in the catalog, in catalog order |

**Per trigger**

| Field | Type | Description |
|---|---|---|
| `trigger_id` | string | Unique trigger identifier |
| `description` | string | Human-readable summary of what causes this trigger |
| `fired` | bool | Whether the activation condition matched this family |
| `source_reference` | object | The form page and section that defines this requirement |
| `requirement_fulfilled` | bool \| null | `null` if not fired; `true` if all instances satisfied; `false` if any instance is missing documents |
| `instances` | array | Empty if not fired; otherwise one entry per scoped instance |

**Per instance**

| Field | Type | Description |
|---|---|---|
| `instance_label` | string | Unique label, e.g. `req_pay_stubs` or `req_household_member_id::James Hartley` |
| `requirement_id` | string | References the requirement catalog |
| `applies_to_member` | string \| null | Member name for `per_member` instances; `null` otherwise |
| `fulfilled` | bool | Whether the document spec is satisfied by the bundle |
| `missing_documents` | array | Document filenames needed to satisfy this instance; empty when fulfilled |

### Deduplication

Some requirements are emitted by two triggers (a checklist trigger and a structured-data sanity overlay — e.g., `trig_checking_checklist` and `trig_checking_structured` both emit `req_checking_statement`). Both triggers appear in the output and both point to the same underlying instance. If the document is present, both show `fulfilled: true`; if absent, both show the same `missing_documents`. The top-level `passed` field counts each unique requirement instance only once.

## Dependencies

`compliance_check.py` delegates core engine logic to `feedback_agent/compliance.py` and adds no new dependencies beyond the Python standard library. No `pip install` required.

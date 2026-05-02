# Catalog Builder Agent

Reads a housing program's source application PDF and produces the **trigger** and **document-set requirement** catalogs that the deterministic compliance engine consumes — same DSL as `catalog_templates/templates.py`.

This agent is one piece of a larger meta-builder pipeline. It is responsible for **catalogs only**. The application input schema (`family_template.json`) and the document-type universe (`bundle_template_total_options.json`) are supplied as CLI inputs; sibling builder agents will eventually generate them from the PDF as well.

## Usage

```bash
python catalog_builder_agent/agent.py \
    --pdf            "Danvers Maple Sq FCFS Application 2026.pdf" \
    --app-template   eval_set_template_jsons/family_template.json \
    --bundle-options eval_set_template_jsons/bundle_template_total_options.json \
    --program-name   "Maple Square FCFS Application 2026" \
    --out            catalogs.json
```

Requires `ANTHROPIC_API_KEY` in the environment (or in a `.env` file at the repo root).

### Inputs

| Flag | Purpose |
|---|---|
| `--pdf` | Source application PDF. Sent to Claude as a native `document` content block. |
| `--app-template` | Application data schema (e.g. `family_template.json`). The agent will only emit predicate `field` paths that resolve inside this schema. |
| `--bundle-options` | Document-type universe. Either a flat JSON array of filenames or a `{bundle_id, documents: [...]}` object. The agent will only emit `document_type` strings drawn from this list. |
| `--program-name` | Human-readable program label, written into every `SourceReference.document` for the audit trail. |
| `--out` | Output JSON path. Default `catalogs.json`. |
| `--model` | Default `claude-sonnet-4-6`. |

### Output

A single JSON file:

```json
{
  "analysis": "one or two sentences from the model: gaps, judgment calls, etc.",
  "triggers": [ <Trigger>, ... ],
  "requirements": [ <DocumentSetRequirement>, ... ]
}
```

`Trigger` and `DocumentSetRequirement` follow the Pydantic schemas in `../catalog_templates/templates.py`. Splitting into separate `trigger_catalog.json` + `req_catalog.json` is left to the operator (e.g. `jq '.triggers' catalogs.json > trigger_catalog.json`).

## Validation

Before returning, the agent runs four structural checks on the model's output and exits non-zero if any fail:

1. **Pydantic** — every entry passes `Trigger.model_validate` / `DocumentSetRequirement.model_validate`.
2. **Cross-references** — every `Trigger.emits_requirements` ID exists in the `requirements` list.
3. **Predicate paths** — every predicate `field` resolves into the supplied app template (per-member-scope paths are checked against the first example member in `household.members`).
4. **Document types** — every `DocumentLeaf.document_type` is a member of the supplied bundle-options list.

These guard against silent garbage. They do NOT validate semantic correctness — that's what the eval is for.

## Deferred for MVP v0

The system prompt teaches the DSL through abstract description only — there is no worked one-shot example in the prompt. **For non-evaluated future programs, inline a known-good catalog as a one-shot example** in the system prompt. This is expected to materially improve fluency and consistency.

We omit it now because Maple Square (the only fully hand-authored program in the repo) is the eval set, and including its catalogs in the prompt would leak ground truth and invalidate the eval.

## Sibling agents (planned, not yet built)

- `app_template_builder_agent` — generates `family_template.json` from a source PDF.
- `bundle_options_builder_agent` — generates the document-type universe from a source PDF.

Once those land, the operator can run all three sequentially and bootstrap a full compliance config for a new program from the PDF alone.

"""
Catalog Builder Agent

Reads a housing program's source application PDF and produces the trigger
and document-set requirement catalogs in the DSL defined by
`catalog_templates/templates.py`.

Inputs (CLI):
  --pdf             Source application PDF
  --app-template    Application data schema (family_template.json shape)
  --bundle-options  Document-type universe (bundle_template_total_options.json
                    shape — either a flat list or {bundle_id, documents: [...]})
  --program-name    Human-readable program label for source_reference.document
  --out             Output JSON path (default: catalogs.json)
  --model           Default: claude-sonnet-4-6

Output: a single JSON file with shape
    {"analysis": str, "triggers": [...], "requirements": [...]}

Requires ANTHROPIC_API_KEY in the environment (or in a .env at repo root).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

# Reach into the sibling catalog_templates package for the Pydantic models.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from catalog_templates.templates import (  # noqa: E402
    DocumentSetRequirement,
    Trigger,
)


class _CatalogOutput(BaseModel):
    """Wrapper for the agent's full response — drives the tool input_schema."""
    analysis: str
    triggers: list[Trigger]
    requirements: list[DocumentSetRequirement]


_OUTPUT_TOOL = {
    "name": "submit_catalog",
    "description": (
        "Submit the trigger and document-set-requirement catalogs derived from "
        "the program PDF. Call this exactly once with the full output."
    ),
    "input_schema": _CatalogOutput.model_json_schema(),
}


# ---------------------------------------------------------------------------
# .env loader (mirrors feedback_agent/agent.py)
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
# Five sections: role, schema reference, DSL semantics, authoring rules, output
# format. No worked example from the eval program (Maple Square) is included —
# see the README's "Deferred for MVP v0" section for why.

_SCHEMA = """\
## Trigger object schema
{
  "trigger_id": "string",
  "description": "string",
  "activation": <Condition>,
  "emits_requirements": ["requirement_id", ...],
  "instance_scope": "household" | "applicant" | "co_applicant" | "per_member",
  "per_member_scope": <Condition> | null,    // required iff instance_scope == "per_member"
  "source_reference": {"document": "str", "page": <int|null>, "section": "str|null", "quote": "str|null"}
}

## DocumentSetRequirement object schema
{
  "requirement_id": "string",
  "description": "string",
  "document_spec": <DocumentSpec>,
  "source_reference": {"document": "str", "page": <int|null>, "section": "str|null", "quote": "str|null"}
}

## Condition node types
{"type": "predicate", "field": "dotted.path", "operator": "equals|not_equals|contains|greater_than|less_than|in|exists", "value": <scalar|list|null>}
{"type": "all",  "children": [<Condition>, ...]}   // AND
{"type": "any",  "children": [<Condition>, ...]}   // OR
{"type": "not",  "child":    <Condition>}

## DocumentSpec node types
{"type": "document", "document_type": "filename.pdf", "notes": <str|null>}
{"type": "all_of",   "children": [<DocumentSpec>, ...]}   // every child required
{"type": "one_of",   "children": [<DocumentSpec>, ...]}   // at least one child required

## Predicate field paths
Dotted paths into the supplied application template JSON. Use ONLY paths that
resolve to a real key in that template. Inside per_member_scope, paths are
relative to a household member object (e.g. "age", "relationship", "name"),
not the household root.
"""


_SYSTEM = f"""\
You are a compliance catalog author. You read a housing program's source application PDF and produce two catalogs — Triggers and DocumentSetRequirements — that a downstream deterministic compliance engine will execute against an applicant's data and document bundle. Your output is consumed by code, not humans; it must be valid JSON matching the schemas below exactly.

The engine evaluates each Trigger's activation predicate against the applicant's structured data. When fired, the trigger emits one or more requirement instances; each instance's document_spec is then evaluated against the applicant's uploaded document bundle. Pass = all instances satisfied. Your job is to encode the program's documentation rules — and only those rules — into this DSL.

Programs in scope include affordable-housing applications (initial leasing) and annual recertifications. Each program has a source PDF that mixes structured form fields with a self-attestation checklist of supporting documents.

# DSL SCHEMA REFERENCE

{_SCHEMA}

# DSL SEMANTICS AND IDIOMS

**Self-attestation pattern.** Most housing applications include a checklist where the applicant initials each supporting-document item that applies to them (pay stubs, voucher, child support, etc.). Expect an `eligibility_checklist.<key>` namespace in the application template; triggers for those items take the form `predicate eligibility_checklist.<key> equals true`. The downstream engine validates that documents match the checklist, not that the checklist is honest.

**Universal triggers.** Some documents are required of every applicant (e.g. signed affidavits, federal tax return). Express these with `household.total_size greater_than 0` as a tautological activation. For per-member universals (e.g. one ID per member), use `instance_scope = "per_member"` with `per_member_scope = {{predicate name exists}}` — a "match all members" no-op.

**Sanity overlay triggers.** When a structured field implies the same requirement as a checklist item (e.g. a non-zero asset balance implies a statement is required), it is fine to emit a second trigger keyed on the structured field that emits the same `requirement_id`. The engine dedupes by instance label. Both paths share one requirement.

**Instance scopes.**
- `household` — one instance, attached to the household.
- `applicant` / `co_applicant` — first-class scopes for the primary applicant and co-applicant. They live outside `household.members[]` in the application schema (typically in `personal_information`, `employment`, etc.) and are not reachable through `per_member_scope`.
- `per_member` — one instance per matching `household.members[]` entry. The validators require `per_member_scope` non-null iff `instance_scope == "per_member"`.

**Per-member scope semantics.** `Predicate.field` inside a `per_member_scope` is interpreted relative to the member object (`age`, `relationship`, `name`), NOT the household root. To gate on cross-cutting household state, put that condition on `Trigger.activation` and use a simple member predicate inside `per_member_scope`.

**Document specs.** A `document` leaf is satisfied by the presence of a matching document type in the bundle. `all_of` requires every child satisfied; `one_of` requires at least one. Specs nest. Choose `one_of` when the PDF says "submit X *or* Y"; choose `all_of` when it says "submit X *and* Y".

**Source references.** Every catalog entry carries a `SourceReference` with the program name, page number, and section/item label from the PDF. This is the audit trail back to the form — never omit page or section.

**MVP non-goals (do NOT try to encode):**
- Document recency / coverage windows / minimum counts ("5 consecutive paystubs", "within last 90 days"). The DSL has no temporal operators. `DocumentLeaf.notes` carries this as advisory free text only.
- Date arithmetic in predicates. There are no "within last N months" operators. Triggers that depend on recency over-fire on any non-null value (use `exists` and accept the over-fire).
- Exclusion / forbidden combinators on `DocumentSpec`. Only `all_of` and `one_of` exist.
- Validating that the applicant's self-attestation is truthful. Out of scope.

**When the application template lacks a signal for a PDF requirement.** If the PDF mandates document X but the supplied application template has no field that would tell the engine whether X applies to this applicant, OMIT the trigger rather than invent a path, and call it out in `analysis`. The downstream engine cannot evaluate predicates against fields that don't exist in the input.

# AUTHORING RULES (HARD CONSTRAINTS)

- `Predicate.field` MUST be a dotted path that resolves inside the supplied application template. Any path the template does not have is invalid.
- `DocumentLeaf.document_type` MUST be a member of the supplied bundle-options list. Do NOT invent strings.
- Every `Trigger` and `DocumentSetRequirement` MUST have a `source_reference` with `document` set to the supplied program name and non-null `page` + `section`.
- Every `Trigger.emits_requirements` ID MUST exist in the `requirements` list you emit. Cross-check before responding.
- IDs MUST be unique within their catalog and use snake_case (`trig_pay_stubs_checklist`, `req_pay_stubs`).

# OUTPUT FORMAT

Submit your output by calling the `submit_catalog` tool exactly once. The tool's input schema is generated from the Pydantic models above and will be enforced by the API — any structural deviation will fail validation. Do not emit any free-text response; the tool call IS the response.

The tool takes three fields:
- `analysis`: one or two sentences — anything the operator should know (gaps where the PDF lacked a template signal, judgment calls on document types, etc.)
- `triggers`: array of full Trigger objects
- `requirements`: array of full DocumentSetRequirement objects
"""


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def _resolve_path(template: Any, dotted: str) -> bool:
    """True iff `dotted` (e.g. "assets.checking") resolves into `template`."""
    cur = template
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False
    return True


def _collect_predicate_fields(condition: dict, into: list[str]) -> None:
    t = condition.get("type")
    if t == "predicate":
        into.append(condition.get("field", ""))
    elif t in ("any", "all"):
        for child in condition.get("children", []) or []:
            _collect_predicate_fields(child, into)
    elif t == "not":
        child = condition.get("child")
        if child is not None:
            _collect_predicate_fields(child, into)


def _collect_doc_types(spec: dict, into: list[str]) -> None:
    t = spec.get("type")
    if t == "document":
        into.append(spec.get("document_type", ""))
    elif t in ("all_of", "one_of"):
        for child in spec.get("children", []) or []:
            _collect_doc_types(child, into)


def _validate_pydantic(triggers: list[dict], requirements: list[dict]) -> list[str]:
    errors: list[str] = []
    for t in triggers:
        try:
            Trigger.model_validate(t)
        except ValidationError as exc:
            errors.append(f"trigger {t.get('trigger_id', '<unknown>')}: pydantic — {exc}")
    for r in requirements:
        try:
            DocumentSetRequirement.model_validate(r)
        except ValidationError as exc:
            errors.append(f"requirement {r.get('requirement_id', '<unknown>')}: pydantic — {exc}")
    return errors


def _check_emits_refs(triggers: list[dict], requirements: list[dict]) -> list[str]:
    req_ids = {r.get("requirement_id") for r in requirements}
    errors: list[str] = []
    for t in triggers:
        tid = t.get("trigger_id", "<unknown>")
        for emit in t.get("emits_requirements", []) or []:
            if emit not in req_ids:
                errors.append(
                    f"trigger {tid}: emits_requirements references unknown id '{emit}'"
                )
    return errors


def _check_predicate_paths(triggers: list[dict], app_template: dict) -> list[str]:
    """Every predicate field path must resolve into the supplied app template."""
    errors: list[str] = []
    members = app_template.get("household", {}).get("members") if isinstance(app_template, dict) else None
    member_template = members[0] if isinstance(members, list) and members else None

    for t in triggers:
        tid = t.get("trigger_id", "<unknown>")

        activation_fields: list[str] = []
        _collect_predicate_fields(t.get("activation") or {}, activation_fields)
        for f in activation_fields:
            if not _resolve_path(app_template, f):
                errors.append(
                    f"trigger {tid}: activation field '{f}' does not resolve in app_template"
                )

        pms = t.get("per_member_scope")
        if pms:
            scope_fields: list[str] = []
            _collect_predicate_fields(pms, scope_fields)
            for f in scope_fields:
                if member_template is None:
                    errors.append(
                        f"trigger {tid}: per_member_scope field '{f}' but app_template has no example member"
                    )
                elif not _resolve_path(member_template, f):
                    errors.append(
                        f"trigger {tid}: per_member_scope field '{f}' does not resolve in member template"
                    )

    return errors


def _check_doc_types(requirements: list[dict], bundle_options: list[str]) -> list[str]:
    allowed = set(bundle_options)
    errors: list[str] = []
    for r in requirements:
        rid = r.get("requirement_id", "<unknown>")
        types: list[str] = []
        _collect_doc_types(r.get("document_spec") or {}, types)
        for d in types:
            if d not in allowed:
                errors.append(
                    f"requirement {rid}: document_type '{d}' not in supplied bundle-options"
                )
    return errors


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def run_catalog_builder(
    pdf_path: Path,
    app_template: dict,
    bundle_options: list[str],
    program_name: str,
    model: str = "claude-sonnet-4-6",
) -> tuple[list[dict], list[dict], str]:
    """Build trigger and requirement catalogs from a program PDF.

    Returns (triggers, requirements, analysis).

    Raises ValueError if the LLM output fails JSON parsing or any of the
    structural validation checks (Pydantic shape, emits_requirements refs,
    allowed predicate paths, allowed document types).
    """
    import anthropic  # lazy: keeps the pure-python validators importable without the SDK

    client = anthropic.Anthropic()

    pdf_b64 = base64.standard_b64encode(pdf_path.read_bytes()).decode("utf-8")

    user_text = (
        f"=== PROGRAM NAME ===\n{program_name}\n\n"
        f"=== APPLICATION TEMPLATE (allowed predicate field paths) ===\n"
        f"{json.dumps(app_template, indent=2)}\n\n"
        f"=== DOCUMENT-TYPE UNIVERSE (allowed document_type strings) ===\n"
        f"{json.dumps(bundle_options, indent=2)}\n\n"
        f"=== SOURCE PDF ===\n(see attached document)"
    )

    user_content = [
        {"type": "text", "text": user_text},
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_b64,
            },
        },
    ]

    response = client.messages.create(
        model=model,
        max_tokens=16384,
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[_OUTPUT_TOOL],
        tool_choice={"type": "tool", "name": _OUTPUT_TOOL["name"]},
        messages=[{"role": "user", "content": user_content}],
    )

    u = response.usage
    print(
        f"  [usage] input={u.input_tokens} output={u.output_tokens} "
        f"cache_created={getattr(u, 'cache_creation_input_tokens', 0)} "
        f"cache_read={getattr(u, 'cache_read_input_tokens', 0)}"
    )

    tool_use = next(
        (b for b in response.content if getattr(b, "type", None) == "tool_use"),
        None,
    )
    if tool_use is None:
        raise ValueError(
            f"LLM did not call submit_catalog (stop_reason={response.stop_reason}); "
            f"content={response.content!r}"
        )

    result: dict = tool_use.input
    triggers: list[dict] = result.get("triggers") or []
    requirements: list[dict] = result.get("requirements") or []
    analysis: str = result.get("analysis", "")

    errors: list[str] = []
    errors.extend(_validate_pydantic(triggers, requirements))
    errors.extend(_check_emits_refs(triggers, requirements))
    errors.extend(_check_predicate_paths(triggers, app_template))
    errors.extend(_check_doc_types(requirements, bundle_options))

    if errors:
        msg = "\n  - ".join([""] + errors)
        raise ValueError(f"Output failed structural validation:{msg}")

    return triggers, requirements, analysis


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Catalog Builder Agent")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--app-template", required=True, dest="app_template")
    parser.add_argument("--bundle-options", required=True, dest="bundle_options")
    parser.add_argument("--program-name", required=True, dest="program_name")
    parser.add_argument("--out", default="catalogs.json")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    args = parser.parse_args()

    app_template = json.loads(Path(args.app_template).read_text())

    bundle_raw = json.loads(Path(args.bundle_options).read_text())
    if isinstance(bundle_raw, dict) and isinstance(bundle_raw.get("documents"), list):
        bundle_options = bundle_raw["documents"]
    elif isinstance(bundle_raw, list):
        bundle_options = bundle_raw
    else:
        raise SystemExit(
            f"--bundle-options must be a list or {{documents: [...]}} object; got {type(bundle_raw).__name__}"
        )

    print(f"Running catalog builder on {args.pdf}...", flush=True)
    triggers, requirements, analysis = run_catalog_builder(
        pdf_path=Path(args.pdf),
        app_template=app_template,
        bundle_options=bundle_options,
        program_name=args.program_name,
        model=args.model,
    )

    Path(args.out).write_text(
        json.dumps(
            {"analysis": analysis, "triggers": triggers, "requirements": requirements},
            indent=2,
        )
    )

    print(f"\nAnalysis: {analysis}")
    print(
        f"Wrote {len(triggers)} triggers and {len(requirements)} requirements to {args.out}"
    )


if __name__ == "__main__":
    main()

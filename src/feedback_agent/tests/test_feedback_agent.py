"""
Feedback Agent — integration tests.

Each test:
  1. Runs compliance_trace on the (family, bundle) pair — confirms it FAILS.
  2. Passes the trace + human feedback to run_feedback_agent.
  3. Runs compliance again on (family, bundle) with updated catalogs — confirms PASS.
  4. Checks the edit was surgical (only the described item changed).

Requires ANTHROPIC_API_KEY in the environment.
Run: python tests/test_feedback_agent.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from compliance import run_compliance, run_compliance_trace
from agent import run_feedback_agent

USECASES = Path(__file__).parent.parent.parent / "usecases"


def _family(n: int) -> dict:
    return json.loads((USECASES / f"family_{n}.json").read_text())


def _bundle(n: int) -> dict:
    return json.loads((USECASES / f"bundle_{n}.json").read_text())


# ---------------------------------------------------------------------------
# Test 1 — req_pay_stubs requires 5 stubs; bundle_3 only has 3.
#
# family_3 (Marcus Webb): pay_stubs.checked=True → trigger fires → req_pay_stubs.
# bundle_3 has pay_stub_1, 2, 3 only — pay_stub_4 and pay_stub_5 are missing.
# Human feedback: only 3 stubs are required, not 5.
# Expected fix: document_spec shrinks from all_of[5] to all_of[3].
# ---------------------------------------------------------------------------

TRIGGERS_T1 = [
    {
        "trigger_id": "trig_pay_stubs",
        "description": "Require pay stubs when applicant self-attests to wage income",
        "activation": {
            "type": "predicate",
            "field": "eligibility_checklist.pay_stubs.checked",
            "operator": "equals",
            "value": True,
        },
        "emits_requirements": ["req_pay_stubs"],
        "instance_scope": "household",
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "section": "Income Verification — Pay Stubs",
        },
    }
]

REQS_T1 = [
    {
        "requirement_id": "req_pay_stubs",
        "description": "Five consecutive pay stubs",
        "document_spec": {
            "type": "all_of",
            "children": [
                {"type": "document", "document_type": "pay_stub_1.pdf"},
                {"type": "document", "document_type": "pay_stub_2.pdf"},
                {"type": "document", "document_type": "pay_stub_3.pdf"},
                {"type": "document", "document_type": "pay_stub_4.pdf"},
                {"type": "document", "document_type": "pay_stub_5.pdf"},
            ],
        },
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "section": "Income Verification — Pay Stubs",
        },
    }
]

FEEDBACK_T1 = (
    "The pay stubs requirement failed because pay_stub_4.pdf and pay_stub_5.pdf were missing. "
    "However, the regulation only requires 3 consecutive pay stubs, not 5. "
    "Marcus Webb submitted pay_stub_1.pdf, pay_stub_2.pdf, and pay_stub_3.pdf — "
    "those three are sufficient and the compliance check should have passed. "
    "Please update the requirement to only require 3 pay stubs."
)


def test_pay_stubs_requirement_fix() -> None:
    family = _family(3)
    bundle = _bundle(3)

    trace = run_compliance_trace(family, bundle, TRIGGERS_T1, REQS_T1)
    assert not trace["passed"], "Expected pre-fix failure"
    assert any(
        r["requirement_id"] == "req_pay_stubs" and not r["satisfied"]
        for r in trace["requirement_trace"]
    ), "Expected req_pay_stubs to be unsatisfied"

    updated_triggers, updated_reqs, analysis = run_feedback_agent(
        trigger_catalog=TRIGGERS_T1,
        req_catalog=REQS_T1,
        bundle=bundle,
        family=family,
        compliance_trace=trace,
        human_feedback=FEEDBACK_T1,
    )
    print(f"\n[T1] Analysis: {analysis}")

    passed_after, failed_after = run_compliance(family, bundle, updated_triggers, updated_reqs)
    assert passed_after, f"Expected post-fix pass, still failing: {failed_after}"

    # Triggers should be untouched
    assert updated_triggers == TRIGGERS_T1, "Triggers should not have changed"

    # req_pay_stubs document_spec must have changed
    updated_spec = next(
        r["document_spec"] for r in updated_reqs if r["requirement_id"] == "req_pay_stubs"
    )
    original_spec = REQS_T1[0]["document_spec"]
    assert updated_spec != original_spec, "document_spec should have changed"

    print("[T1] PASS")


# ---------------------------------------------------------------------------
# Test 2 — trig_federal_tax_returns fires on employment presence (bug);
#           should fire on checklist field.
#
# family_4 (Priya Patel): has employer → employment.date_of_hire exists → trigger fires.
# But eligibility_checklist.federal_tax_returns_2024.checked = False.
# bundle_4 has no federal_tax_return_2024.pdf → FAIL.
# Human feedback: trigger should be keyed to the checklist, not employment.
# Expected fix: activation field changes to checklist path.
# After fix: checklist=False → trigger doesn't fire → no req emitted → PASS.
# ---------------------------------------------------------------------------

TRIGGERS_T2 = [
    {
        "trigger_id": "trig_federal_tax_returns",
        "description": "Require federal tax returns",
        "activation": {
            "type": "predicate",
            "field": "employment.date_of_hire",
            "operator": "exists",
        },
        "emits_requirements": ["req_federal_tax_returns"],
        "instance_scope": "household",
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "section": "Income Verification — Tax Returns",
        },
    }
]

REQS_T2 = [
    {
        "requirement_id": "req_federal_tax_returns",
        "description": "Most recent federal tax return (2024)",
        "document_spec": {
            "type": "document",
            "document_type": "federal_tax_return_2024.pdf",
        },
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "section": "Income Verification — Tax Returns",
        },
    }
]

FEEDBACK_T2 = (
    "The federal tax returns trigger incorrectly fired for Priya Patel. "
    "The trigger is keyed to employment.date_of_hire being present, but that is wrong — "
    "it should only fire when the applicant checked the federal_tax_returns_2024 item "
    "on their eligibility checklist (eligibility_checklist.federal_tax_returns_2024.checked). "
    "Priya did not check that box, so the trigger should not have fired at all. "
    "Please fix the trigger activation to use the checklist field."
)


def test_federal_tax_trigger_fix() -> None:
    family = _family(4)
    bundle = _bundle(4)

    trace = run_compliance_trace(family, bundle, TRIGGERS_T2, REQS_T2)
    assert not trace["passed"], "Expected pre-fix failure"
    assert any(
        t["trigger_id"] == "trig_federal_tax_returns" and t["fired"]
        for t in trace["trigger_trace"]
    ), "Expected trig_federal_tax_returns to have fired"

    updated_triggers, updated_reqs, analysis = run_feedback_agent(
        trigger_catalog=TRIGGERS_T2,
        req_catalog=REQS_T2,
        bundle=bundle,
        family=family,
        compliance_trace=trace,
        human_feedback=FEEDBACK_T2,
    )
    print(f"\n[T2] Analysis: {analysis}")

    passed_after, failed_after = run_compliance(family, bundle, updated_triggers, updated_reqs)
    assert passed_after, f"Expected post-fix pass, still failing: {failed_after}"

    # Requirements should be untouched
    assert updated_reqs == REQS_T2, "Requirements should not have changed"

    # Trigger activation must reference the checklist field now
    updated_activation = next(
        t["activation"] for t in updated_triggers
        if t["trigger_id"] == "trig_federal_tax_returns"
    )
    activation_str = json.dumps(updated_activation)
    assert "federal_tax_returns_2024" in activation_str, (
        f"Updated activation should reference checklist field, got: {activation_str}"
    )

    print("[T2] PASS")


# ---------------------------------------------------------------------------
# Test 3 — req_household_member_id only accepts birth_certificate.pdf (bug);
#           driver_license and passport are also valid.
#
# Custom bundle has driver_license.pdf but no birth_certificate.pdf.
# Buggy req → FAIL.
# Human feedback: driver_license.pdf should be accepted.
# Expected fix: document_spec becomes one_of including driver_license.
# After fix: driver_license.pdf in bundle → PASS.
# ---------------------------------------------------------------------------

TRIGGERS_T3 = [
    {
        "trigger_id": "trig_household_member_id",
        "description": "Always require household member identification",
        "activation": {
            "type": "predicate",
            "field": "household.total_size",
            "operator": "greater_than",
            "value": 0,
        },
        "emits_requirements": ["req_household_member_id"],
        "instance_scope": "household",
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "section": "Required Documents — Identification",
        },
    }
]

REQS_T3 = [
    {
        "requirement_id": "req_household_member_id",
        "description": "Government-issued photo identification",
        "document_spec": {
            "type": "document",
            "document_type": "birth_certificate.pdf",
        },
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "section": "Required Documents — Identification",
        },
    }
]

# Bundle with a driver's license but no birth certificate
BUNDLE_T3 = {
    "bundle_id": "bundle_test3",
    "documents": [
        "driver_license.pdf",
        "pay_stub_1.pdf",
        "pay_stub_2.pdf",
        "pay_stub_3.pdf",
        "pay_stub_4.pdf",
        "pay_stub_5.pdf",
        "federal_tax_return_2024.pdf",
        "checking_statement_march2025.pdf",
    ],
}

FEEDBACK_T3 = (
    "The household member ID requirement failed because the bundle contained driver_license.pdf "
    "but the requirement only accepts birth_certificate.pdf. "
    "The Maple Square application accepts any government-issued photo ID — "
    "a driver's license is valid identification and should satisfy this requirement. "
    "Please update the requirement to also accept driver_license.pdf and passport.pdf "
    "as alternatives to birth_certificate.pdf."
)


def test_household_id_requirement_fix() -> None:
    family = _family(5)
    bundle = BUNDLE_T3

    trace = run_compliance_trace(family, bundle, TRIGGERS_T3, REQS_T3)
    assert not trace["passed"], "Expected pre-fix failure"
    assert any(
        r["requirement_id"] == "req_household_member_id" and not r["satisfied"]
        for r in trace["requirement_trace"]
    )

    updated_triggers, updated_reqs, analysis = run_feedback_agent(
        trigger_catalog=TRIGGERS_T3,
        req_catalog=REQS_T3,
        bundle=bundle,
        family=family,
        compliance_trace=trace,
        human_feedback=FEEDBACK_T3,
    )
    print(f"\n[T3] Analysis: {analysis}")

    passed_after, failed_after = run_compliance(family, bundle, updated_triggers, updated_reqs)
    assert passed_after, f"Expected post-fix pass, still failing: {failed_after}"

    # Triggers should be untouched
    assert updated_triggers == TRIGGERS_T3, "Triggers should not have changed"

    # document_spec must now accept driver_license.pdf
    updated_spec = next(
        r["document_spec"] for r in updated_reqs if r["requirement_id"] == "req_household_member_id"
    )
    assert updated_spec["type"] == "one_of", (
        f"Expected one_of document_spec, got {updated_spec['type']!r}"
    )
    doc_types = {c["document_type"] for c in updated_spec["children"]}
    assert "driver_license.pdf" in doc_types, (
        f"driver_license.pdf should be in updated spec, got: {doc_types}"
    )

    print("[T3] PASS")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        ("Test 1 — pay_stubs req (5→3 stubs, family_3/bundle_3)",        test_pay_stubs_requirement_fix),
        ("Test 2 — federal_tax trigger (employment→checklist, family_4)", test_federal_tax_trigger_fix),
        ("Test 3 — household_id req (birth_cert→one_of, family_5)",       test_household_id_requirement_fix),
    ]

    passed = failed = 0
    for name, fn in tests:
        print(f"\n{'='*60}\n{name}\n{'='*60}")
        try:
            fn()
            passed += 1
        except Exception as exc:
            import traceback
            print(f"FAILED: {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)

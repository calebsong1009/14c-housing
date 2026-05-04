from __future__ import annotations
from typing import Dict, List, Tuple, Any
import sys
from pathlib import Path
import json
# Support running from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from compliance_checker.compliance_check import build_report

TriggerDict = Dict[str, Dict[str, Any]]


def check_doc(family_app_filepath, document_bundle_filepath) -> Tuple[bool, TriggerDict]:
    """
    Runs document eligibility checks.

    Replace the body of this function with your real external checker call.

    Parameters
    ----------
    application_file:
        A single uploaded file object from Streamlit.
    document_bundle_files:
        A list of uploaded file objects from Streamlit.

    Returns
    -------
    tuple
        (overall_pass, triggers)
        - overall_pass: bool
        - triggers: dict shaped like
          {
              trigger_id: {
                  "pass": bool,
                  "description": str,
                  "document_requirement_id": list,
              }
          }
    """
    family = json.loads(Path(family_app_filepath).read_text(encoding="utf-8"))
    bundle = json.loads(Path(document_bundle_filepath).read_text(encoding="utf-8"))
    triggers = json.loads(Path(args.trigger_catalog).read_text(encoding="utf-8"))
    reqs = json.loads(Path(args.req_catalog).read_text(encoding="utf-8"))

    report = build_report(family, bundle, triggers, reqs)
    report = build_report()
    # Example placeholder behavior for MVP wiring.
    # Swap this out with your real implementation.
    bundle_count = len(document_bundle_files)

    triggers: TriggerDict = {
        "trigger_001": {
            "pass": application_file is not None,
            "description": "Application file was provided.",
            "document_requirement_id": ["app_required"],
        },
        "trigger_002": {
            "pass": bundle_count > 0,
            "description": "At least one supporting document was uploaded.",
            "document_requirement_id": ["bundle_required"],
        },
        "trigger_003": {
            "pass": bundle_count >= 2,
            "description": "Bundle contains at least two documents for demonstration purposes.",
            "document_requirement_id": ["demo_multi_doc_rule"],
        },
    }

    overall_pass = all(trigger["pass"] for trigger in triggers.values())
    return overall_pass, triggers

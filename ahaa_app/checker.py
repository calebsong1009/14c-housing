from __future__ import annotations

from typing import Dict, List, Tuple, Any


TriggerDict = Dict[str, Dict[str, Any]]


def check_doc(application_file, document_bundle_files) -> Tuple[bool, TriggerDict]:
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

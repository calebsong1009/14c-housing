import json
from html import escape
from pathlib import Path

import streamlit.components.v1 as components


STATUS_STYLES = {
    True: {
        "background": "#e7f7ed",
        "border": "#23a455",
        "text": "#135c2d",
        "icon": "checkmark",
        "symbol": "✓",
    },
    False: {
        "background": "#fdebea",
        "border": "#d93025",
        "text": "#8c1d18",
        "icon": "x",
        "symbol": "✕",
    },
}


def _eval_feedback_js():
    return (Path(__file__).with_name("eval_feedback.js")).read_text()


def _json_script_payload(value):
    return json.dumps(value).replace("</", "<\\/")


def _requirement_items(requirement_ids):
    if not requirement_ids:
        return "<li>None</li>"

    return "\n".join(f"<li>{escape(str(req_id))}</li>" for req_id in requirement_ids)


def _trigger_card(trigger_data, index, eval_mode=False):
    passed = bool(trigger_data["requirement_fulfilled"])
    raw_description = trigger_data.get("description", "No description provided.")
    source_ref = trigger_data.get("source_reference", {})
    style = STATUS_STYLES[passed]
    header = f"{index}. {raw_description}"
    escaped_header = escape(header, quote=True)
    feedback_key = str(index) if eval_mode else ""

    # get display for all missing docs
    missing_docs_field = ""
    if not passed:
        # all_missing_docs = []
        # for instance in trigger_data.get('instances',[]):
        #     if bool(instance['fulfilled']) == False:
        #         member = instance.get("applies_to_member", "")
        #         member = "" if (member is None) or (member.isin(['null',''])) else (member+' - ')
        #         all_missing_docs.extend([f'{member}'+doc for doc in instance.get('missing_documents',[])])
        all_missing_docs = trigger_data.get("all_missing_docs",[])
        missing_docs_field = f"""<p><strong>Missing Documents:</strong></p>
                <ul>{_requirement_items(all_missing_docs)}</ul>
                <p></p>
                """
        
    flag_button = ""
    feedback_field = ""
    trigger_id = ""
    if eval_mode:
        flag_button = f"""
            <button
                aria-label="Flag {escaped_header} for evaluation"
                class="flag-button"
                data-flag-button="{feedback_key}"
                data-feedback-key="{feedback_key}"
                data-feedback-title="{escaped_header}"
                type="button"
            >
                ⚑
            </button>
        """
        feedback_field = f"""
            <div class="feedback-field">
                <label for="trigger-feedback-{feedback_key}">Feedback:</label>
                <textarea
                    data-feedback-input="{feedback_key}"
                    id="trigger-feedback-{feedback_key}"
                    placeholder="If this requirement appears incorrect, please flag it and provide a brief explanation."
                    rows="3"
                ></textarea>
            </div>
        """
        trigger_id = f"""
            <p><strong>Trigger ID:</strong> {str(trigger_data['trigger_id'])}</p>
        """

    return f"""
        <details class="trigger-card" style="border-color: {style["border"]};">
            <summary
                class="trigger-summary"
                style="background: {style["background"]}; color: {style["text"]};"
            >
                <span aria-label="{style["icon"]}" class="status-symbol">{style["symbol"]}</span>
                {escaped_header}
            </summary>
            <div class="trigger-body">
                <div class="trigger-body-header">
                    <p><strong>Requirement Passed:</strong> {str(passed)}</p>
                    {flag_button}
                </div>
                {missing_docs_field}
                <p><strong>Application Guideline Reference:</strong></p>
                <p>This requirement was extracted from the <i>{source_ref.get("document", "unknown")}</i> document, page {source_ref.get("page", "unknown")}, section "{source_ref.get("section", "unknown")}".</p>
                {trigger_id}
                {feedback_field}
            </div>
        </details>
    """


def _trigger_count_height(triggers, eval_mode=False):
    requirement_count = 0
    for trigger_data in triggers:
        requirement_ids = trigger_data.get("document_requirement_id", [])
        requirement_count += len(requirement_ids) if requirement_ids else 1

    base = 460 if eval_mode else 140
    per_trigger = 330 if eval_mode else 175
    min_height = 520 if eval_mode else 220

    return max(min_height, base + len(triggers) * per_trigger + requirement_count * 28)


def _shared_css():
    return """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                margin: 0;
            }

            details {
                box-sizing: border-box;
            }

            summary {
                cursor: pointer;
                list-style-position: inside;
            }

            .status-row {
                align-items: center;
                display: flex;
                gap: 0.5rem;
                margin: 0 0 0.75rem;
            }

            .status-banner {
                border-left: 0.45rem solid;
                border-radius: 0.35rem;
                flex: 1;
                font-size: 1.35rem;
                font-weight: 700;
                line-height: 1.35;
                padding: 0.8rem 1rem;
            }

            .status-value {
                font-weight: 800;
            }

            .flag-button {
                align-items: center;
                background: #f7f7f8;
                border: 1px solid #c8ccd2;
                border-radius: 0.35rem;
                color: #8b9099;
                cursor: pointer;
                display: inline-flex;
                flex: 0 0 auto;
                font-size: 1rem;
                height: 2.1rem;
                justify-content: center;
                line-height: 1;
                width: 2.1rem;
            }

            .status-row .flag-button {
                font-size: 1.05rem;
                height: 2.4rem;
                width: 2.4rem;
            }

            .flag-button.flagged {
                background: #fdebea;
                border-color: #d93025;
                color: #d93025;
            }

            .feedback-field {
                margin: 0 0 1rem;
            }

            .trigger-body .feedback-field {
                margin: 0.9rem 0 0;
            }

            .feedback-field label {
                color: #262730;
                display: block;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .feedback-field textarea {
                border: 1px solid #c8ccd2;
                border-radius: 0.35rem;
                box-sizing: border-box;
                color: #262730;
                font: inherit;
                line-height: 1.4;
                min-height: 5rem;
                padding: 0.55rem 0.65rem;
                resize: none;
                width: 100%;
            }

            .trigger-details {
                border: 1px solid #d9dde3;
                border-radius: 0.35rem;
                overflow: hidden;
            }

            .trigger-details > summary {
                background: #f6f7f9;
                color: #262730;
                font-size: 1.2rem;
                font-weight: 700;
                padding: 0.8rem 1rem;
            }

            .trigger-list {
                padding: 0.25rem 1rem 0.9rem;
            }

            .trigger-card {
                border: 1px solid;
                border-radius: 0.35rem;
                margin: 0.75rem 0;
                overflow: hidden;
            }

            .trigger-summary {
                font-size: 1.05rem;
                font-weight: 700;
                line-height: 1.35;
                padding: 0.7rem 0.85rem;
            }

            .status-symbol {
                margin-right: 0.35rem;
            }

            .trigger-body {
                color: #262730;
                font-size: 1rem;
                line-height: 1.45;
                padding: 0.75rem 1rem 0.95rem;
            }

            .trigger-body p {
                margin: 0 0 0.6rem;
            }

            .trigger-body-header {
                align-items: center;
                display: flex;
                gap: 0.5rem;
                justify-content: space-between;
            }

            .trigger-body ul {
                margin: 0.2rem 0 0;
                padding-left: 1.25rem;
            }

            .feedback-flags {
                border: 1px solid #d9dde3;
                border-radius: 0.35rem;
                margin-top: 1rem;
                padding: 0.9rem 1rem 1rem;
            }

            .feedback-flags h3 {
                color: #262730;
                font-size: 1.15rem;
                margin: 0 0 0.75rem;
            }

            .feedback-flags-header {
                align-items: center;
                display: flex;
                gap: 0.75rem;
                justify-content: space-between;
                margin-bottom: 0.75rem;
            }

            .feedback-flags-header h3 {
                margin: 0;
            }

            .save-button {
                background: #262730;
                border: 1px solid #262730;
                border-radius: 0.35rem;
                color: #ffffff;
                cursor: pointer;
                font: inherit;
                font-weight: 700;
                line-height: 1;
                padding: 0.5rem 0.75rem;
            }

            .save-button:disabled {
                cursor: not-allowed;
                opacity: 0.55;
            }

            .save-status {
                color: #4b5563;
                font-size: 0.9rem;
                margin: 0.5rem 0 0;
                min-height: 1.2rem;
            }

            .empty-feedback {
                color: #6b7280;
                font-size: 0.95rem;
            }

            .feedback-item {
                border-left: 0.25rem solid #d93025;
                margin: 0.75rem 0;
                padding-left: 0.75rem;
            }

            .feedback-item-title {
                color: #262730;
                font-weight: 700;
                line-height: 1.35;
            }

            .feedback-item-text {
                color: #4b5563;
                margin-top: 0.35rem;
                white-space: pre-wrap;
            }
        </style>
    """


def _status_banner_html(label, passed, include_flag=False):
    style = STATUS_STYLES[bool(passed)]
    if passed:
        display_text = "✓ Application Complete - all supporting documents are present."
    else:
        display_text = '✕ Application Incomplete - missing supporting documents.'
    flag_button = ""
    if include_flag:
        flag_button = """
            <button
                aria-label="Flag Document bundle passed for evaluation"
                class="flag-button"
                data-bundle-flag
                type="button"
            >
                ⚑
            </button>
        """

    return f"""
        <div class="status-row">
            <div
                class="status-banner"
                style="
                    background: {style["background"]};
                    border-left-color: {style["border"]};
                    color: {style["text"]};
                "
            >
                {escape(str(display_text))}
            </div>
            {flag_button}
        </div>
    """


def render_status_banner(label, passed, missing_docs):
    components.html(
        f"{_shared_css()}{_status_banner_html(label, passed)}",
        height=84,
        scrolling=False,
    )


def render_trigger_details_accordion(triggers):
    trigger_content = "".join(
        _trigger_card(trigger_data, index)
        for index, trigger_data in enumerate(triggers)
    )
    height = _trigger_count_height(triggers)

    components.html(
        f"""
        {_shared_css()}
        <details class="trigger-details">
            <summary>Document Requirement Details</summary>
            <div class="trigger-list">{trigger_content}</div>
        </details>
        """,
        height=height,
        scrolling=False,
    )


def render_eval_results(
    overall_pass,
    triggers,
    missing_docs,
    feedback_save_url,
    family_app_filepath,
    doc_bundle_filepath,
):
    trigger_content = "".join(
        _trigger_card(trigger_data, index, eval_mode=True)
        for index, (trigger_data) in enumerate(triggers)
    )
    if not trigger_content:
        trigger_content = '<div class="empty-feedback">No triggers were returned.</div>'

    components.html(
        f"""
        {_shared_css()}
        {_status_banner_html("Document bundle passed", overall_pass, include_flag=True)}

        <div class="feedback-field">
            <label for="overall-feedback">Overall Feedback</label>
            <textarea
                data-overall-feedback
                id="overall-feedback"
                placeholder="If this result appears incorrect, please flag it and provide a brief explanation for review."
                rows="3"
            ></textarea>
        </div>

        <details class="trigger-details">
            <summary>Document Requirement Details</summary>
            <div class="trigger-list">{trigger_content}</div>
        </details>

        <section class="feedback-flags">
            <div class="feedback-flags-header">
                <h3>Feedback Flags</h3>
                <button
                    class="save-button"
                    data-save-feedback
                    data-save-url="{escape(str(feedback_save_url), quote=True)}"
                    type="button"
                >
                    Save
                </button>
            </div>
            <div class="empty-feedback">No feedback flags yet.</div>
            <div class="feedback-list"></div>
            <div class="save-status" data-save-status></div>
        </section>

        <script type="application/json" data-eval-results>
            {_json_script_payload({
                "overall_pass": bool(overall_pass),
                "triggers": triggers,
                "source_files": {
                    "family_application": str(family_app_filepath),
                    "document_bundle": str(doc_bundle_filepath),
                },
            })}
        </script>
        <script>{_eval_feedback_js()}</script>
        """,
        height=_trigger_count_height(triggers, eval_mode=True),
        scrolling=False,
    )

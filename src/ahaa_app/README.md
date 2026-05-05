# HAHA Streamlit App

## Files

- `app.py`: Main Streamlit app. Runs `check_doc()` to get application completion check results. Includes 2 UI modes: regular and eval.
- `checker.py`: Wrapper for compliance checker. `check_doc()` loads the family application, document bundle, trigger catalog, and requirement catalog, runs `build_report()`, and returns:
  - `overall_pass`: whether the application bundle passed.
  - `triggers`: fired trigger objects from the report.
  - `total_missing_docs`: deduplicated list of missing documents for top-level display.
- `ui_components.py`: HTML/CSS rendering helpers for the status banner, missing documents card, trigger details accordion, and Eval Mode feedback UI.
- `eval_feedback.js`: Browser-side JavaScript for Eval Mode. It tracks flagged results, collects textarea feedback, and posts the final feedback payload to the local feedback server.
- `feedback_server.py`: Starts a small local HTTP server that receives Eval Mode feedback and writes it to disk.
- `saved_feedback/`: Output folder for saved Eval Mode runs. Each save creates a new subfolder containing the copied source inputs and `feedback.json`.
- `requirements.txt`: Python dependencies for running the app.

## Run Locally

From the `14c-housing/src/ahaa_app` directory:

```bash
pip install -r requirements.txt
streamlit run app.py
```

You can also run it from the repository root:

```bash
streamlit run 14c-housing/src/ahaa_app/app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`.

## Current Data Flow

The upload form requires one application file and at least one supporting document before the check runs. At the moment, the app uses hardcoded bundled test cases from `evals/usecases` using `get_test_filepaths()` rather than the uploaded files.

```python
family_app_filepath, doc_bundle_filepath, trigger_catalog_filepath, req_catalog_filepath = get_test_filepaths(id)
```

`check_doc()` then loads:

- `evals/usecases/family_{id}.json`
- `evals/usecases/bundle_{id}.json`
- `catalog_templates/trigger_catalog.json`
- `catalog_templates/req_catalog.json`

After the checker runs, the app displays an application complete/incomplete status banner. Under that banner, it shows the missing documents returned from `check_doc()`.

## Eval Mode

Eval Mode is a review workflow for collecting human feedback on checker results. Turn it on with the `Eval Mode` toggle before clicking `Check`.

In Eval Mode, the app shows:

- The same complete/incomplete status banner and missing documents card.
- An overall feedback textarea for comments about the full result.
- A flag button on the overall result.
- A trigger details accordion with a flag button and feedback textarea for each fired trigger.
- A `Feedback Flags` panel showing the currently flagged items.
- A `Save` button.

Flagging a result adds it to the feedback payload. The feedback textareas let reviewers explain why the overall result or a trigger result appears wrong or needs attention.

## Saved Feedback

When Eval Mode feedback is saved, `eval_feedback.js` posts the payload to the local server created by `feedback_server.py`.

The server writes each save to:

```text
saved_feedback/<family_id>_<bundle_id>_<random_id>/
```

Each saved feedback folder contains:

- `family_application.json`: copy of the family application used for the check.
- `document_bundle.json`: copy of the document bundle used for the check.
- `feedback.json`: reviewer feedback, flagged items, overall pass/fail value, and trigger data.

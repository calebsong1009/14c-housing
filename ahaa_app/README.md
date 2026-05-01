# AHAA MVP

## Files
- `app.py`: Streamlit UI
- `checker.py`: `check_doc()` function is a dummy placeholder for actually running compliance engine check.
- `requirements.txt`: minimal dependency list

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Jay's TODOs
1. Edit `checker.py` and replace the placeholder implementation inside `check_doc()`. This function should be the actual compliance engine check.

Current expected return format:
```python
overall_pass: bool
triggers = {
    "trigger_id": {
        "pass": bool,
        "description": "Some description",
        "document_requirement_id": ["req_1", "req_2"],
    }
}
```

This needs to be updated to reflect actual Trigger Objects.

2. Create method to save feedback from Eval Mode. 
```python
feedback_flags:{
    overall_flagged: True
    overall_feedback: str,
    triggers = {
        "trigger_id": {
        "flagged": True,
        "flag_feedback": str,
        "pass": bool,
        "description": "Some description",
        "document_requirement_id": ["req_1", "req_2"],
    }
    }
}
```

Something like this? Format needs to be changed to reflect actual Trigger Object format. 


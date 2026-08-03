# Federal IRV legacy backup app

Run the frozen backup separately with:

```bash
streamlit run app_legacy.py
```

The backup uses `data/legacy_app`, restores the archived manual preference-flow
and scenario evidence, disables evidence shrinkage, nearest-field matching and
seat-class effects, and never synchronises Google Sheets. The development app
continues to use `app.py` and `data/raw`.

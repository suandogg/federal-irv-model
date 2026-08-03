from __future__ import annotations

import os


os.environ["FEDERAL_IRV_APP_MODE"] = "legacy"

# Streamlit executes this module as the entry point. Importing the shared UI
# after setting the mode keeps the backup visually identical while routing all
# model reads to the frozen legacy snapshot.
import app  # noqa: E402,F401

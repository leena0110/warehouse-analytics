"""
startup.py — Azure App Service startup script.
Sets the working directory correctly when Azure runs the app.
"""
import os
import sys

# Ensure backend directory is in Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.main import app  # noqa: F401 — re-exported for uvicorn

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("startup:app", host="0.0.0.0", port=port, reload=False)

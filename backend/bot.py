"""
Run either of these — they start the identical application:
    uvicorn main:app --host 0.0.0.0 --port 8080
    uvicorn bot:app  --host 0.0.0.0 --port 8080
"""
from main import app

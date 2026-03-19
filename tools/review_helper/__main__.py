"""Entry point: python -m review_helper"""
import uvicorn
from .main import create_app

app = create_app()
uvicorn.run(app, host="127.0.0.1", port=8021)

#!/bin/bash
# Application startup script for Render

# Install dependencies first
pip install -r requirements.txt

# Start the application
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
#!/bin/bash
cd "$(dirname "$0")"
lsof -ti:8000 | xargs kill -9 2>/dev/null
uvicorn app.main:app --reload --port 8000

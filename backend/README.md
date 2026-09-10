# Priva Backend

This is the Builder B backend starter for the Priva hackathon project.

## What is included

- FastAPI app scaffold
- Basic health and status endpoints
- Mock data for positions, PnL, risk usage, activity log, strategies, and kill switch
- Render deployment config for a free-tier backend

## Run locally

```bash
cd c:\Users\odusa\Desktop\Priva
C:/Users/odusa/anaconda3/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then open:

- http://127.0.0.1:8001/health
- http://127.0.0.1:8001/status
- http://127.0.0.1:8001/positions
- http://127.0.0.1:8001/strategies

## Main files

- app/main.py — FastAPI app and mock API routes
- requirements.txt — Python dependencies
- render.yaml — Render deployment config

## Current status

This matches the Day 1 milestone from the project brief: the app is live as a backend skeleton with mock data, ready for real market-data and paper-trading work next.

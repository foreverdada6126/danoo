from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import asyncio
from typing import Dict, Any

app = FastAPI(title="DaNoo - Strategy Intelligence Engine v5.2")
app.mount("/static", StaticFiles(directory="web_ui/static"), name="static")
templates = Jinja2Templates(directory="web_ui/templates")

# State holders (to be updated by the engine)
SYSTEM_STATE = {
    "status": "OPERATIONAL",
    "regime": "RANGING",
    "equity": 12450.75,
    "pnl_24h": +2.5,
    "active_orders": 2,
    "symbol": "BTCUSDT",
    "trend": "NEUTRAL",
    "rsi": 45.2,
    "timeframe": "15m"
}

# Mock logs for the UI
LOG_HISTORY = [
    {"time": "15:42:01", "msg": "Engine Initialized: DaNoo v5.2"},
    {"time": "15:45:10", "msg": "Data Continuity Check: 1000 candles verified."},
    {"time": "15:48:30", "msg": "Regime Shift Detected: BULL_TREND confirmed via 1h TF."},
]

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "state": SYSTEM_STATE})

@app.get("/api/status")
async def get_status():
    return SYSTEM_STATE

@app.get("/api/logs")
async def get_logs():
    return LOG_HISTORY

@app.get("/api/chart")
async def get_chart_data():
    # Mock data for the performance chart
    return {
        "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "values": [12100, 12250, 12200, 12350, 12400, 12420, 12450]
    }

@app.post("/api/chat")
async def chat_with_openclaw(msg: ChatMessage):
    # This would link to the OpenClaw skill agent logic
    # Simplified mock response for now
    response = f"OpenClaw: I received your instruction: '{msg.message}'. Analyzing market impact..."
    return {"reply": response}

def start_ui_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    return server

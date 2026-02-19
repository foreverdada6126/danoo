import os
import shutil
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from config.settings import SETTINGS
import uvicorn
import asyncio
from typing import Dict, Any, List
import psutil
import platform
import time

app = FastAPI(title="DaNoo - Strategy Intelligence Engine v5.2")

class ChatMessage(BaseModel):
    message: str

# Define storage directories
REFERENCE_DIR = "reference_files"
DATA_DIR = "data/processed"

@app.get("/api/files")
async def list_files():
    """List files in reference_files and data/processed."""
    ref_files = os.listdir(REFERENCE_DIR)
    data_files = os.listdir(DATA_DIR)
    return {
        "reference": ref_files,
        "processed_data": data_files
    }

@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...), target: str = "reference"):
    """Upload a file to the specified target directory."""
    path = REFERENCE_DIR if target == "reference" else DATA_DIR
    file_path = os.path.join(path, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename, "status": "uploaded"}

@app.delete("/api/files/{filename}")
async def delete_file(filename: str, target: str = "reference"):
    """Delete a file from the specified directory."""
    path = REFERENCE_DIR if target == "reference" else DATA_DIR
    file_path = os.path.join(path, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"status": "deleted"}
    return {"status": "not_found"}

import subprocess

@app.get("/api/system/info")
async def get_system_info():
    """Returns version and git status."""
    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
        git_msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"]).decode().strip()
    except:
        git_hash = "no-git"
        git_msg = "Unknown"
        
    return {
        "version": SETTINGS.VERSION,
        "git_hash": git_hash,
        "last_commit": git_msg,
        "mode": SETTINGS.MODE
    }

@app.post("/api/system/git_sync")
async def git_sync():
    """Pushes local changes to GitHub."""
    try:
        # Simple sync: add, commit, push
        # In a real scenario, you'd want a message input, but for 'simple sync' we automate
        subprocess.run(["git", "add", "."], check=True)
        # Check if there are changes to commit
        status = subprocess.check_output(["git", "status", "--porcelain"]).decode().strip()
        if status:
            subprocess.run(["git", "commit", "-m", "Sync from DaNoo Web UI"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        return {"status": "success", "message": "Pushed to GitHub successfully."}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Git Error: {str(e)}"}

@app.get("/api/logs")
async def get_logs():
    return LOG_HISTORY
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
    "timeframe": "15m",
    "ai_insight": "Awaiting initial research...",
    "sentiment_score": 0.0
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

@app.get("/api/system/health")
async def get_health():
    """Returns VPS health metrics."""
    return {
        "cpu_usage": psutil.cpu_percent(interval=None),
        "ram_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "uptime": int(time.time() - psutil.boot_time()),
        "platform": platform.system()
    }

@app.post("/api/system/cleanup")
async def run_cleanup():
    """Performs basic housekeeping (clearing logs)."""
    try:
        LOG_HISTORY.clear()
        LOG_HISTORY.append({"time": time.strftime("%H:%M:%S"), "msg": "Housekeeping: Logs cleared."})
        return {"status": "success", "message": "Housekeeping complete. Logs cleared."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/chart")
async def get_chart_data():
    # Mock data for the performance chart
    return {
        "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "values": [12100, 12250, 12200, 12350, 12400, 12420, 12450]
    }

@app.post("/api/engine/scan")
async def trigger_scan():
    """Manually triggers a fresh regime scan."""
    try:
        # In a real engine, this would call engine.run_regime_scan()
        # For now, we update the log to show the bot responded
        LOG_HISTORY.append({"time": time.strftime("%H:%M:%S"), "msg": "Manual Command: Depth Market Regime Scan initiated."})
        return {"status": "success", "message": "Regime scan triggered."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

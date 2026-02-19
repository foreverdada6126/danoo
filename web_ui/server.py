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
import httpx
from loguru import logger

# --- Real-time Log Bridge ---
def ui_log_sink(message):
    """Pushes every 'logger.info' from the terminal into the Dashboard UI."""
    try:
        record = message.record
        log_entry = {
            "time": record["time"].strftime("%H:%M:%S"),
            "msg": record["message"]
        }
        # Avoid circular imports if possible, but since we are in server.py it works
        LOG_HISTORY.append(log_entry)
        if len(LOG_HISTORY) > 50: LOG_HISTORY.pop(0)
    except:
        pass

# Add the sink (but not if already added)
logger.add(ui_log_sink, format="{message}", level="INFO")

# To see host metrics from inside a container with /host/proc mounted
os.environ["PROCFS_PATH"] = "/host/proc"

app = FastAPI(title="DaNoo - Strategy Intelligence Engine v5.2")

class ChatMessage(BaseModel):
    message: str

# Define storage directories
REFERENCE_DIR = "reference_files"
DATA_DIR = "data/processed"

@app.get("/api/files")
async def list_files():
    """List files in reference_files and data/processed."""
    os.makedirs(REFERENCE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
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

from config.settings import SETTINGS

# State holders (to be updated by the engine)
SYSTEM_STATE = {
    "status": "OPERATIONAL",
    "mode": SETTINGS.MODE.upper(),
    "regime": "RANGING",
    "equity": 1000.0,
    "pnl_24h": +2.5,
    "active_orders": 0,
    "symbol": "BTCUSDT",
    "trend": "NEUTRAL",
    "rsi": 45.2,
    "timeframe": "15m",
    "ai_insight": "Awaiting initial research...",
    "sentiment_score": 0.0,
    "heartbeat": "IDLE"
}

# Mock data for the dashboard refinement
ACTIVE_TRADES = []
APPROVAL_QUEUE = [
    {"time": time.time(), "signal": "Vol-Breakout High", "sentiment": 0.82, "status": "AWAITING APPROVAL"}
]
EQUITY_HISTORY = [1000.0]

@app.get("/api/chart")
async def get_chart_data():
    """Returns the history of equity for the Performance chart."""
    # Ensure current equity is the last item
    if not EQUITY_HISTORY or EQUITY_HISTORY[-1] != SYSTEM_STATE["equity"]:
        EQUITY_HISTORY.append(SYSTEM_STATE["equity"])
    
    # Return last 50 points
    history = EQUITY_HISTORY[-50:]
    return {
        "labels": [f"T-{len(history)-i-1}" for i in range(len(history))],
        "values": history
    }

LOG_HISTORY = []
RECON_HISTORY = []

@app.get("/api/system/trades")
async def get_active_trades():
    return {"trades": ACTIVE_TRADES}

@app.get("/api/system/approvals")
async def get_approval_queue():
    return {"approvals": APPROVAL_QUEUE}

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "state": SYSTEM_STATE})

@app.get("/api/status")
async def get_status():
    """Returns the core system state (equity, regime, insights)."""
    # Dynamic sync of order count for the UI counter
    SYSTEM_STATE["active_orders"] = len(ACTIVE_TRADES)
    return SYSTEM_STATE

@app.get("/api/system/health")
async def get_health():
    """Returns VPS health metrics with a small interval for accuracy."""
    return {
        "cpu_usage": psutil.cpu_percent(interval=0.1),
        "ram_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "uptime": int(time.time() - psutil.boot_time()),
        "platform": platform.system()
    }

@app.get("/api/system/report")
async def get_system_report():
    """Executes system commands to provide the 'manage.sh' style full report."""
    try:
        cpu = subprocess.check_output(["top", "-bn1"]).decode().split('\n')[2]
        mem = subprocess.check_output(["free", "-h"]).decode()
        disk = subprocess.check_output(["df", "-h", "/"]).decode()
        containers = subprocess.check_output(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"]).decode()
        
        report = f"--- CPU VITAL ---\n{cpu}\n\n--- MEMORY VITAL ---\n{mem}\n--- DISK VITAL ---\n{disk}\n--- CONTAINER FLEET ---\n{containers}"
        return {"report": report}
    except Exception as e:
        return {"report": f"Report Generation Error: {str(e)}"}

@app.get("/api/system/recon")
async def get_recon_history():
    """Returns the history of intelligence reconnaissance reports."""
    return {"recon": RECON_HISTORY}

@app.post("/api/system/cleanup")
async def run_cleanup():
    """Performs basic housekeeping (clearing logs)."""
    try:
        LOG_HISTORY.clear()
        LOG_HISTORY.append({"time": time.time(), "msg": "Housekeeping: Logs cleared."})
        return {"status": "success", "message": "Housekeeping complete. Logs cleared."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/system/approve/{signal_id}")
async def approve_trade(signal_id: int):
    """Approves a pending trade signal from the queue."""
    try:
        if 0 <= signal_id < len(APPROVAL_QUEUE):
            approved = APPROVAL_QUEUE.pop(signal_id)
            # Simulate execution entry
            new_trade = {
                "time": time.time(),
                "symbol": "BTC/USDT",
                "type": "LONG (PAPER)",
                "status": "OPEN",
                "pnl": "+$0.02"
            }
            ACTIVE_TRADES.insert(0, new_trade)
            # Update equity history to show impact on chart
            SYSTEM_STATE["equity"] += 0.02
            LOG_HISTORY.append({"time": time.time(), "msg": f"EXECUTION: Approved trade for {approved['signal']}"})
            return {"status": "success", "message": "Trade approved and executed."}
        return {"status": "error", "message": "Signal not found."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/engine/recon")
async def trigger_recon():
    """Forwards a manual research request to the Intel Service."""
    try:
        async with httpx.AsyncClient() as client:
            # Tell the scientist to run a manual 'Full Scan'
            await client.post("http://intel-service:5000/api/research/analyze", json={
                "query": "Manual Institutional Depth Scan: Bitcoin",
                "context": "" # Will fetch fresh web data
            })
        LOG_HISTORY.append({"time": time.time(), "msg": "Manual Recon: Scientist dispatched for BTC depth scan."})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/engine/scan")
async def trigger_scan():
    """Manually triggers a fresh regime scan."""
    try:
        # In a real engine, this would call engine.run_regime_scan()
        # For now, we update the log to show the bot responded
        LOG_HISTORY.append({"time": time.time(), "msg": "Manual Command: Depth Market Regime Scan initiated."})
        return {"status": "success", "message": "Regime scan triggered."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/chat")
async def chat_with_openclaw(msg: ChatMessage):
    logger.info(f"Chat Message Received: {msg.message[:50]}...")
    # Detect autonomous reports from the Intel Service
    if "SCIENTIST_REPORT:" in msg.message:
        payload = msg.message.split("SCIENTIST_REPORT:")[1].strip()
        logger.info(f"Scientist Report Detected. Payload: {payload[:100]}...")
        
        # Super-resilient parsing: find the LAST two pipes to extract Score and Regime
        # Format: [Long Justification] | [Score] | [Regime]
        parts = [p.strip() for p in payload.split("|")]
        
        if len(parts) >= 3:
            # The last part is Regime, second to last is Score. Everything else is Justification.
            regime_raw = parts[-1].replace("Regime:", "").strip()
            score_raw = parts[-2].replace("Score:", "").strip()
            # Join everything before the score as the justification
            justification = "|".join(parts[:-2]).replace("Justification:", "").strip()
            
            try:
                # Clean up score (removes letters/labels)
                import re
                score_clean = re.findall(r"[-+]?\d*\.\d+|\d+", score_raw)[0]
                score = float(score_clean)
            except:
                score = 0.0
                
            # Update State
            SYSTEM_STATE["ai_insight"] = justification
            SYSTEM_STATE["sentiment_score"] = score
            SYSTEM_STATE["regime"] = regime_raw
            
            report_time = time.time()
            LOG_HISTORY.append({"time": report_time, "msg": f"AI Intelligence: {justification[:50]}..."})
            
            # Update Recon History
            RECON_HISTORY.append({
                "time": report_time,
                "title": f"SCAN REPORT - BTC/{regime_raw}",
                "content": justification,
                "score": score
            })
            if len(RECON_HISTORY) > 20: RECON_HISTORY.pop(0)

            # 4. Trigger Approval Queue for High Conviction Signals (> 0.7 or < -0.7)
            if abs(score) >= 0.7:
                signal_type = "LONG" if score > 0 else "SHORT"
                APPROVAL_QUEUE.append({
                    "time": time.strftime("%H:%M"),
                    "signal": f"AI-{signal_type} ({regime_raw})",
                    "sentiment": score,
                    "status": "AWAITING APPROVAL"
                })
                LOG_HISTORY.append({"time": report_time, "msg": f"STRATEGIC ALERT: High Conviction {signal_type} signal detected. Check Approval Queue."})

            logger.info(f"Recon Card Created: {regime_raw} | {score}")
            return {"status": "success", "message": "Intelligence Dossier Updated."}

    # Standard user chat logic
    response = f"OpenClaw: I received your instruction: '{msg.message}'. Analyzing market impact..."
    return {"reply": response}

def start_ui_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    return server

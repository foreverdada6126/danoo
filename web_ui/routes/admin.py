"""
Admin Routes - Config, files, git sync, AI toggle, chat, recon, engine triggers.
"""
import os
import re
import shutil
import time
import asyncio
import subprocess
import httpx
from typing import Dict
from fastapi import APIRouter, UploadFile, File
from loguru import logger
from pydantic import BaseModel
from config.settings import SETTINGS
from database.models import DB_SESSION, Trade, CandleCache
from web_ui.state import SYSTEM_STATE, LOG_HISTORY, RECON_HISTORY, APPROVAL_QUEUE
from datetime import datetime

router = APIRouter()

class ChatMessage(BaseModel):
    message: str

REFERENCE_DIR = "reference_files"
DATA_DIR = "data/processed"

# ─── File Management ─────────────────────────────────────────────

@router.get("/api/files")
async def list_files():
    """List files in reference_files and data/processed."""
    os.makedirs(REFERENCE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    return {
        "reference": os.listdir(REFERENCE_DIR),
        "processed_data": os.listdir(DATA_DIR)
    }

@router.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...), target: str = "reference"):
    """Upload a file to the specified target directory."""
    path = REFERENCE_DIR if target == "reference" else DATA_DIR
    file_path = os.path.join(path, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename, "status": "uploaded"}

@router.delete("/api/files/{filename}")
async def delete_file(filename: str, target: str = "reference"):
    """Delete a file from the specified directory."""
    path = REFERENCE_DIR if target == "reference" else DATA_DIR
    file_path = os.path.join(path, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"status": "deleted"}
    return {"status": "not_found"}

# ─── Config & Control ────────────────────────────────────────────

@router.post("/api/system/config")
async def update_config(data: Dict[str, str]):
    """Updates the global asset or timeframe."""
    if "symbol" in data:
        new_symbol = data["symbol"]
        SYSTEM_STATE["symbol"] = new_symbol
        SETTINGS.DEFAULT_SYMBOL = new_symbol
        LOG_HISTORY.append({"time": time.time(), "msg": f"SYSTEM: Asset switched to {new_symbol}. Re-init scanning..."})
        return {"status": "success", "symbol": new_symbol}
    
    if "timeframe" in data:
        new_tf = data["timeframe"]
        SYSTEM_STATE["timeframe"] = new_tf
        SETTINGS.DEFAULT_TIMEFRAME = new_tf
        LOG_HISTORY.append({"time": time.time(), "msg": f"SYSTEM: Timeframe switched to {new_tf}. Recalculating indicators..."})
        return {"status": "success", "timeframe": new_tf}
    
    if "mode" in data:
        new_mode = data["mode"].upper()
        if new_mode in ["PAPER", "LIVE", "WALK_FORWARD"]:
            SYSTEM_STATE["mode"] = new_mode
            SETTINGS.MODE = new_mode.lower()
            try:
                from scheduler import SCALPER
                if hasattr(SCALPER, "executor"):
                    SCALPER.executor.mode = new_mode.lower()
                    SCALPER.executor.setup_exchange()
            except Exception as e:
                logger.error(f"Failed to propagate mode change: {e}")
            LOG_HISTORY.append({"time": time.time(), "msg": f"SYSTEM: Execution mode switched to {new_mode}."})
            return {"status": "success", "mode": new_mode}
            
    if "strat_toggle" in data:
        strat = data["strat_toggle"]
        if strat in ["strat_strict", "strat_loose", "strat_recon"]:
            SYSTEM_STATE[strat] = not SYSTEM_STATE.get(strat, False)
            status_str = "ENABLED" if SYSTEM_STATE[strat] else "DISABLED"
            logger.info(f"UI Toggle: Strategy {strat} {status_str}")
            LOG_HISTORY.append({"time": time.time(), "msg": f"SYSTEM: Strategy {strat.replace('strat_','').upper()} is now {status_str}."})
            return {"status": "success", strat: SYSTEM_STATE[strat]}
    
    return {"status": "error", "message": "Invalid config keys"}

@router.post("/api/system/toggle_ai")
async def toggle_ai_state():
    """Enables or disables OpenAI calls globally."""
    SYSTEM_STATE["ai_active"] = not SYSTEM_STATE["ai_active"]
    status = "ACTIVE" if SYSTEM_STATE["ai_active"] else "DISABLED"
    LOG_HISTORY.append({"time": time.time(), "msg": f"SYSTEM: AI Communication has been {status}."})
    return {"status": "success", "ai_active": SYSTEM_STATE["ai_active"]}

@router.post("/api/system/git_sync")
async def git_sync():
    """Pushes local changes to GitHub."""
    try:
        subprocess.run(["git", "add", "."], check=True)
        status = subprocess.check_output(["git", "status", "--porcelain"]).decode().strip()
        if status:
            subprocess.run(["git", "commit", "-m", "Sync from DaNoo Web UI"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        return {"status": "success", "message": "Pushed to GitHub successfully."}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Git Error: {str(e)}"}

# ─── Data Collection ─────────────────────────────────────────────

@router.post("/api/data/collect")
async def collect_historical_data(payload: dict):
    from core.data_collector import HistoricalDataCollector
    
    symbol = payload.get("symbol", "BTCUSDT")
    interval = payload.get("interval", "1m")
    start_year = int(payload.get("start_year", 2023))
    end_year = int(payload.get("end_year", 2023))
    
    collector = HistoricalDataCollector()
    LOG_HISTORY.append({"time": time.time(), "msg": f"SYSTEM: Initiated historical data sync for {symbol} ({start_year}-{end_year})..."})
    
    asyncio.create_task(collector.collect_async(symbol, interval, start_year, end_year))
    
    return {"status": "success", "message": f"Started background download for {symbol}."}

# ─── Intelligence & Recon ────────────────────────────────────────

@router.get("/api/system/recon")
async def get_recon_history():
    """Returns the history of intelligence recon reports grouped by date."""
    from sqlalchemy import desc
    
    grouped = {}
    session = DB_SESSION()
    
    if not RECON_HISTORY:
        session.close()
        return {"recon_groups": []}
        
    sorted_recon = sorted(RECON_HISTORY, key=lambda x: x.get('time', 0), reverse=True)
    
    for item in sorted_recon:
        dt = datetime.fromtimestamp(item['time'])
        date_key = dt.strftime("%Y-%m-%d")
        
        if date_key not in grouped:
            end_of_day = datetime.combine(dt.date(), datetime.max.time())
            candle = session.query(CandleCache).filter(
                CandleCache.timestamp <= end_of_day
            ).order_by(desc(CandleCache.timestamp)).first()
            closing_price = candle.close if candle else 0.0
            
            start_of_day = datetime.combine(dt.date(), datetime.min.time())
            trades = session.query(Trade).filter(
                Trade.exit_time >= start_of_day,
                Trade.exit_time <= end_of_day,
                Trade.status == 'CLOSED'
            ).all()
            daily_pnl = sum((t.pnl or 0.0) for t in trades) if trades else 0.0
            
            grouped[date_key] = {
                "date": dt.strftime("%b %d, %Y"),
                "date_id": date_key,
                "closing_price": closing_price,
                "daily_pnl": daily_pnl,
                "items": []
            }
        
        grouped[date_key]["items"].append(item)
    
    session.close()
    
    result = []
    sorted_keys = sorted(grouped.keys(), reverse=True)
    for key in sorted_keys:
        result.append(grouped[key])
        
    return {"recon_groups": result}

@router.post("/api/engine/recon")
async def trigger_recon():
    """Forwards a manual research request to the Intel Service."""
    if not SYSTEM_STATE["ai_active"]:
        return {"status": "error", "message": "AI Communication is currently DISABLED. Enable it to run scans."}
        
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://intel-service:5000/api/research/analyze", json={
                "query": "Manual Institutional Depth Scan: Bitcoin",
                "context": ""
            })
        LOG_HISTORY.append({"time": time.time(), "msg": "Manual Recon: Scientist dispatched for BTC depth scan."})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/engine/scan")
async def trigger_scan():
    """Manually triggers a fresh regime scan."""
    try:
        LOG_HISTORY.append({"time": time.time(), "msg": "Manual Command: Depth Market Regime Scan initiated."})
        return {"status": "success", "message": "Regime scan triggered."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ─── AI Chat Interface ───────────────────────────────────────────

@router.post("/api/chat")
async def chat_with_openclaw(msg: ChatMessage):
    logger.info(f"Chat Message Received: {msg.message[:50]}...")
    
    if "SCIENTIST_REPORT:" in msg.message:
        payload = msg.message.split("SCIENTIST_REPORT:")[1].strip()
        logger.info(f"Scientist Report Detected. Payload: {payload[:100]}...")
        
        parts = [p.strip() for p in payload.split("|")]
        
        regime_raw = "INFO"
        score = 0.0
        justification = payload
        
        if len(parts) >= 3:
            regime_raw = parts[-1].replace("Regime:", "").strip()
            score_raw = parts[-2].replace("Score:", "").strip()
            justification = "|".join(parts[:-2]).replace("Justification:", "").strip()
            try:
                score_clean = re.findall(r"[-+]?\d*\.\d+|\d+", score_raw)[0]
                score = float(score_clean)
            except: score = 0.0
        else:
            score_match = re.search(r"(?:Score|Sentiment|Conviction):\s*([-+]?\d*\.?\d+)", payload, re.I)
            if score_match: score = float(score_match.group(1))
            
            regime_match = re.search(r"(?:Regime|Condition):\s*(\w+)", payload, re.I)
            if regime_match: regime_raw = regime_match.group(1).upper()
            
            justification = payload.replace("**High-Level Summary:**", "").strip()

        SYSTEM_STATE["ai_insight"] = justification[:200] + "..."
        SYSTEM_STATE["sentiment_score"] = score
        if regime_raw != "INFO": SYSTEM_STATE["regime"] = regime_raw
        
        report_time = time.time()
        LOG_HISTORY.append({"time": report_time, "msg": f"AI Intelligence: {justification[:50]}...", "cat": "CORE"})
        
        RECON_HISTORY.append({
            "time": report_time,
            "title": f"INTEL REPORT - {regime_raw}",
            "content": justification,
            "score": score
        })
        if len(RECON_HISTORY) > 20: RECON_HISTORY.pop(0)

        if abs(score) >= 0.7:
            signal_type = "LONG" if score > 0 else "SHORT"
            APPROVAL_QUEUE.append({
                "time": time.time(),
                "signal": f"AI-{signal_type} ({regime_raw})",
                "sentiment": score,
                "status": "AWAITING APPROVAL",
                "reason": justification
            })
            LOG_HISTORY.append({"time": report_time, "msg": f"STRATEGIC ALERT: High Conviction {signal_type} signal detected. Check Approval Queue."})

        logger.info(f"Recon Card Created: {regime_raw} | {score}")
        return {"status": "success", "message": "Intelligence Dossier Updated."}

    response = f"OpenClaw: I received your instruction: '{msg.message}'. Analyzing market impact..."
    return {"reply": response}

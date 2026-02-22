"""
Status & System Routes - Health, status, system info, reports.
"""
import time
import psutil
import platform
import subprocess
from fastapi import APIRouter
from loguru import logger
from web_ui.state import SYSTEM_STATE, LOG_HISTORY, ACTIVE_TRADES

router = APIRouter()

@router.get("/api/status")
async def get_status():
    """Returns the core system state (equity, regime, insights)."""
    SYSTEM_STATE["active_orders"] = len(ACTIVE_TRADES)
    return SYSTEM_STATE

@router.get("/api/system/health")
async def get_health():
    """Returns VPS health metrics."""
    return {
        "cpu_usage": psutil.cpu_percent(interval=0.1),
        "ram_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "uptime": int(time.time() - psutil.boot_time()),
        "platform": platform.system()
    }

@router.get("/api/system/info")
async def get_system_info():
    """Returns version and git status."""
    from config.settings import SETTINGS
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

@router.get("/api/system/report")
async def get_system_report():
    """Executes system commands for a full report."""
    try:
        cpu = subprocess.check_output(["top", "-bn1"]).decode().split('\n')[2]
        mem = subprocess.check_output(["free", "-h"]).decode()
        disk = subprocess.check_output(["df", "-h", "/"]).decode()
        containers = subprocess.check_output(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"]).decode()
        report = f"--- CPU VITAL ---\n{cpu}\n\n--- MEMORY VITAL ---\n{mem}\n--- DISK VITAL ---\n{disk}\n--- CONTAINER FLEET ---\n{containers}"
        return {"report": report}
    except Exception as e:
        return {"report": f"Report Generation Error: {str(e)}"}

@router.get("/api/logs")
async def get_logs():
    return LOG_HISTORY

@router.post("/api/system/cleanup")
async def run_cleanup():
    """Performs basic housekeeping (clearing logs)."""
    try:
        LOG_HISTORY.clear()
        LOG_HISTORY.append({"time": time.time(), "msg": "Housekeeping: Logs cleared."})
        return {"status": "success", "message": "Housekeeping complete. Logs cleared."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

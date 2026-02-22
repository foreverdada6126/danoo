from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger
import uvicorn
import os
import httpx
import asyncio
import time
from config.settings import SETTINGS

app = FastAPI(title="DaNoo Intel Service - Headless Scientist v5.2")

# Initialize LangChain model - Switched to gpt-4o-mini for 90% cost reduction
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Simple Research Cache to prevent redundant costs
RESEARCH_CACHE = {} 
CACHE_TTL = 900 # 15 minutes

# Productivity Stats
REPORT_STATS = {} # YYYY-MM-DD -> count

def log_activity():
    """Increments the report counter for the current day."""
    day = time.strftime("%Y-%m-%d")
    REPORT_STATS[day] = REPORT_STATS.get(day, 0) + 1

class ResearchRequest(BaseModel):
    query: str
    context: str = ""

@app.get("/", response_class=HTMLResponse)
async def scientist_status():
    """Funny status page for the Headless Scientist."""
    has_brain = bool(SETTINGS.OPENAI_API_KEY)
    status_color = "#00ff64" if has_brain else "#ff4444"
    status_text = "HYPER-ACTIVE" if has_brain else "BRAIN-DEAD"
    flavor_sub = "Caffeinated and Analyzing." if has_brain else "Forgot to plug in my brain (Check .env)."
    
    html_content = f"""
    <html>
        <head>
            <title>DaNoo Scientist Portal</title>
            <style>
                body {{ background: #050608; color: #d1d4dc; font-family: 'Inter', 'Courier New', monospace; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; overflow: hidden; }}
                .container {{ border: 1px solid rgba(255,255,255,0.08); padding: 50px; border-radius: 30px; background: rgba(17, 21, 28, 0.7); backdrop-filter: blur(20px); box-shadow: 0 20px 80px rgba(0,0,0,0.8); text-align: center; max-width: 500px; }}
                h1 {{ color: #00f2ff; letter-spacing: 2px; text-transform: lowercase; font-weight: 800; font-size: 28px; margin-bottom: 20px; }}
                h1 span {{ font-style: italic; color: #fff; }}
                .status-badge {{ display: inline-block; padding: 6px 20px; border-radius: 50px; background: {status_color}15; color: {status_color}; border: 1px solid {status_color}33; font-weight: 900; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; }}
                .terminal {{ background: rgba(0,0,0,0.4); padding: 25px; border-radius: 15px; margin-top: 30px; text-align: left; font-size: 13px; border: 1px solid rgba(255,255,255,0.05); color: #888; line-height: 1.6; }}
                .cursor {{ display: inline-block; width: 8px; height: 15px; background: #00f2ff; animation: blink 1s infinite; vertical-align: middle; }}
                @keyframes blink {{ 0%, 50% {{ opacity: 1; }} 51%, 100% {{ opacity: 0; }} }}
                .glow {{ color: #00f2ff; text-shadow: 0 0 10px rgba(0,242,255,0.5); }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>da<span>noo</span> scientist</h1>
                <div class="status-badge">{status_text}</div>
                <div class="terminal">
                    > Accessing neural clusters...<br>
                    > Objective: BTC Sentiment Analysis<br>
                    > <span class="glow">Mood:</span> {flavor_sub}<br><br>
                    <span style="color: #444;">--- PRODUCTIVITY LOG ---</span><br>
                    {"".join([f"> {d}: {c} reports<br>" for d, c in sorted(REPORT_STATS.items(), reverse=True)[:5]])}
                    {"> No data yet." if not REPORT_STATS else ""}
                    <br>
                    <span style="color: #444;">------------------------------</span><br>
                    > <span style="color: #fff">Lab Status:</span> All systems nominal. I am watching the markets so you don't have to. <span class="cursor"></span>
                </div>
            </div>
        </body>
    </html>
    """
    return html_content

async def fetch_serper_data(query: str):
    """Fetches real-time web context via Serper.dev."""
    if not SETTINGS.SERPER_API_KEY:
        logger.warning("SERPER_API_KEY missing. Skipping web research.")
        return "No web data available."
    
    url = "https://google.serper.dev/search"
    payload = {"q": query}
    headers = {
        'X-API-KEY': SETTINGS.SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            results = response.json()
            # Extract snippets for context
            snippets = [f"{item.get('title')}: {item.get('snippet')}" for item in results.get('organic', [])[:5]]
            return "\n".join(snippets)
        except Exception as e:
            logger.error(f"Serper error: {e}")
            return "Web research failed."

async def run_autonomous_research():
    """Autonomous loop that scans BTC sentiment every hour."""
    while True:
        try:
            logger.info("Scientist: Starting autonomous BTC market scan...")
            
            # 1. Fetch Web Context
            context = await fetch_serper_data("Bitcoin latest market sentiment and technical outlook")
            
            # 2. Analyze with AI
            prompt = ChatPromptTemplate.from_template("""
            You are the DaNoo Senior Analyst. 
            Latest Market Context: {context}
            
            Based on this information, provide:
            1. A Sentiment Score (-1.0 to +1.0)
            2. A one-sentence institutional justification.
            3. Identify the current 'Regime' (BULL_TREND, BEAR_TREND, RANGING).
            
            FORMAT: Justification | Score | Regime
            """)
            
            chain = prompt | llm
            response = chain.invoke({"context": context})
            result_text = response.content
            
            # Extract sentiment for metadata
            sentiment = 0.0
            if "|" in result_text:
                try:
                    parts = result_text.split("|")
                    if len(parts) >= 2:
                        import re
                        score_clean = re.findall(r"[-+]?\d*\.\d+|\d+", parts[-2])[0]
                        sentiment = float(score_clean)
                except: pass

            # 3. Push findings to DaNoo Core Dashboard
            async with httpx.AsyncClient() as client:
                # Target A: DaNoo Core Dashboard
                try:
                    await client.post("http://danoo-core:8000/api/chat", json={
                        "message": f"SCIENTIST_REPORT: {result_text}"
                    })
                except:
                    logger.warning("Could not reach danoo-core. Dashboard update skipped.")

                # Target B: Mission Control Webhook (The Executive Office)
                if SETTINGS.MISSION_CONTROL_WEBHOOK:
                    try:
                        # Determine status based on sentiment
                        status = "Review" if abs(sentiment) > 0.4 else "Inbox"
                        priority = "High" if abs(sentiment) > 0.7 else "Normal"
                        
                        target_url = f"http://{os.getenv('VPS_IP', 'localhost')}:8001{SETTINGS.MISSION_CONTROL_WEBHOOK}"
                        headers = {"Authorization": f"Bearer {SETTINGS.LOCAL_AUTH_TOKEN}"} if SETTINGS.LOCAL_AUTH_TOKEN else {}
                        
                        await client.post(target_url, json={
                            "query": "Autonomous BTC Research",
                            "analysis": result_text,
                            "metadata": {
                                "source": "DaNoo-Scientist", 
                                "timestamp": time.time(),
                                "status": status,
                                "priority": priority
                            }
                        }, headers=headers)
                        logger.info(f"Scientist: Report sent to Mission Control ({status}/{priority}).")
                    except Exception as mc_err:
                        logger.warning(f"Failed to push to Mission Control: {mc_err}")

            logger.info(f"Scientist: Scan completed. Findings: {result_text}")
            log_activity()
            
        except Exception as e:
            logger.error(f"Autonomous scan error: {e}")
        
        # Wait 1 hour before next scan
        await asyncio.sleep(3600)

@app.post("/api/research/analyze")
async def analyze_market(req: ResearchRequest):
    """Manual trigger for research with caching to reduce costs."""
    logger.info(f"Manual Research Triggered: {req.query}")
    
    # 1. Check Cache
    cache_key = f"{req.query}_{time.strftime('%Y-%m-%d_%H')}" # Hour-level grouping
    if cache_key in RESEARCH_CACHE:
        cached_data, timestamp = RESEARCH_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info("Cost Optimization: Serving from Research Cache.")
            return {"analysis": cached_data, "status": "CACHED"}

    try:
        # 2. If no context provided, fetch it
        context = req.context if req.context else await fetch_serper_data(req.query)
        
        prompt = ChatPromptTemplate.from_template("""
        You are the DaNoo Intel Analyzer. 
        Context: {context}
        Query: {query}
        
        Return a high-level summary and sentiment estimate.
        
        FORMAT YOUR RESPONSE WITH THESE HEADERS AT THE END:
        Justification: [Quick Summary]
        Sentiment Score: [Value -1.0 to 1.0]
        Current Regime: [BULL_TREND/BEAR_TREND/RANGING]
        """)
        
        chain = prompt | llm
        response = chain.invoke({"context": context, "query": req.query})
        result_text = response.content
        
        # 3. Update Cache
        RESEARCH_CACHE[cache_key] = (result_text, time.time())
        
        # 4. Push to dashboard 
        async with httpx.AsyncClient() as client:
            try:
                # The result_text already contains the pipes from the prompt
                logger.info("Scientist: Pushing manual scan result to dashboard...")
                resp = await client.post("http://danoo-core:8000/api/chat", json={
                    "message": f"SCIENTIST_REPORT: {result_text}"
                })
                logger.info(f"Scientist: Push status: {resp.status_code}")
                log_activity()
            except Exception as push_err:
                logger.error(f"Scientist: Failed to push to dashboard: {push_err}")

        return {
            "analysis": result_text,
            "status": "COMPLETED"
        }
    except Exception as e:
        logger.error(f"Research error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Start the autonomous researcher in the background."""
    asyncio.create_task(run_autonomous_research())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)

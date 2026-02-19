from fastapi import FastAPI, HTTPException, BackgroundTasks
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

class ResearchRequest(BaseModel):
    query: str
    context: str = ""

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

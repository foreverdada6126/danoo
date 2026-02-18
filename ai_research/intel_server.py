from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger
import uvicorn
import os

app = FastAPI(title="DaNoo Intel Service - LangChain Core")

# Initialize LangChain model
# Note: In a real VPS, this would use the env var
llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)

class ResearchRequest(BaseModel):
    query: str
    context: str = ""

@app.post("/api/research/analyze")
async def analyze_market(req: ResearchRequest):
    logger.info(f"Researching: {req.query}")
    try:
        prompt = ChatPromptTemplate.from_template("""
        You are the DaNoo Intel Analyzer. 
        Context: {context}
        Query: {query}
        
        Analyze the provided data and return a sentiment score between -1.0 (Very Bearish) and +1.0 (Very Bullish) 
        and a brief institutional-grade justification.
        """)
        
        chain = prompt | llm
        response = chain.invoke({"context": req.context, "query": req.query})
        
        return {
            "analysis": response.content,
            "sentiment_estimate": 0.5, # Logic to extract from content could go here
            "status": "COMPLETED"
        }
    except Exception as e:
        logger.error(f"Research error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)

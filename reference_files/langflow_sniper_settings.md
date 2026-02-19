# DaNoo v5.2 - Langflow "AI Sniper" Strategy Blueprint

Use these settings to connect your **Langflow Lab (Port 32771)** to your **Trading Engine (Port 8000)**.

## Node 1: Social Discovery (Search)
- **Component**: Google Search / Serper
- **Input Query**: "What are the top 5 trending AI cryptocurrency tokens right now on Twitter/X?"

## Node 2: Technical Filter (Python / CCXT)
- **Logic**: 
  1. Take symbols from Node 1.
  2. Fetch RSI (14 period) on 15m or 1h timeframe.
  3. Filter for symbols where **RSI < 40**.

## Node 3: Reasoning (OpenAI / LLM)
- **Component**: ChatOpenAI
- **System Prompt**: "You are the Lead Strategist for DaNoo. Analyze the social trending coins and their technical RSI levels. Identify the single best opportunity for a 'Mean Reversion' trade."

## Node 4: The Integration (HTTP Request)
- **Target URL**: `http://intel-service:5000/api/research/analyze`
- **Method**: `POST`
- **JSON Payload**:
```json
{
  "query": "Langflow AI Sniper Signal",
  "context": "Trending AI tokens filtered. Best candidate: {LLM_Result}"
}
```

---

## 🏆 The Result
When this flow executes, the **AI INSIGHT** card on your DaNoo Dashboard (Port 8000) will instantly update with the results of your Langflow research.

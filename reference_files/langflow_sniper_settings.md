# DaNoo v5.2 - "BTC Direct" Strategy Blueprint

Use these settings to focus exclusively on Bitcoin for your first live run.

## Node 1: BTC Context (Search)
- **Component**: Serper / Google Search
- **Input Query**: "Bitcoin latest market sentiment and technical analysis for today"

## Node 2: The Brain (OpenAI / LLM)
- **Component**: ChatOpenAI
- **System Prompt**: "You are the Senior BTC Strategist. Based on the search results: {data}, identify if the current Bitcoin mood is 'Optimistic' or 'Cautionary'. Support it with one data point found."

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

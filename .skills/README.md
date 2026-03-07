# 🛠️ OpenClaw Skills Directory

This directory contains specialized scripts and "skills" used by the **OpenClaw Meta-Agent**. 

## ⚖️ Skill Audit Policy
To maintain the integrity of the Institutional Meta Allocation Engine, all skills must adhere to the following governance:

1. **Discovery Only**: Skills should primarily be used for data discovery, research, and analysis. They should NOT have direct execution authority unless explicitly routed through the `ExecutionEngine`.
2. **Line-by-Line Review**: Any new skill or modification to an existing one requires a manual audit of the code logic.
3. **Pinned Versions**: Use specific library versions if external dependencies are required.
4. **No Side Effects**: Skills must avoid un-logged state changes or external network requests outside of authorized API endpoints.

## 📂 Template Structure
Every skill should follow this basic structure:
```python
"""
Skill: [Skill Name]
Role: [Purpose of the skill]
Governance: [Audit Link/Status]
"""

async def execute(*args, **kwargs):
    # Core logic here
    pass
```

## 🚀 Active Skills
- [Pending Audit] `market_discovery.py`
- [Pending Audit] `sentiment_analyzer.py`

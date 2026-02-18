# Crypto Engine V5

An advanced, AI-powered cryptocurrency trading engine designed for multi-timeframe regime analysis, risk-aware execution, and automated portfolio management.

## Core Architecture

- **Regime Engine**: Analyzes market conditions across multiple timeframes.
- **AI Layer**: Meta-reviews strategy performance and provides explainable confidence models.
- **Risk Engine**: Real-time risk parameter enforcement and portfolio allocation.
- **Execution Engine**: Smart order routing and cost modeling.
- **Monitoring**: Integrated health checks and anomaly detection.
- **Security**: Sandbox skills and key management.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Configure settings in `config/settings.py` and `secrets.env`.
3. Run the application: `python app.py`

## Accessing the Web UI

When running on a VPS, the Web UI is accessible at:
- `http://<vps-ip>:8000`

The UI allows you to monitor equity, market regime, and issue instructions directly to OpenClaw via the **Intel Interface** chat.

Refer to the directory layout for module descriptions.

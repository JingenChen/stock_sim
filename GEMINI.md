# GEMINI.md - Project Context & Instructions

This project is a minimalist **A-Share Virtual Trading System** designed for local simulation. It features a FastAPI backend, a Vue 3 frontend, and uses local files for data persistence.

## Project Overview

- **Purpose**: Simulates A-share trading rules (T+1 settlement, commissions, stamp duty) using real-time market data from Sina Finance.
- **Backend**: Python 3.14+ with FastAPI.
- **Frontend**: Single-page Vue 3 application (`index.html`).
- **Data Storage**:
  - `data.json`: Stores account balance, current positions, and active (pending) orders.
  - `history.csv`: Stores historical transaction records (trade log).
- **Core Engine**: A background thread in `main.py` polls market data every 3 seconds and matches pending orders based on current prices and conditional rules.

## Building and Running

### Prerequisites
- Python 3.14+
- `pip`

### Installation
```bash
# Create a virtual environment (optional)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install fastapi uvicorn requests
```

### Running the Server
```bash
python3 main.py
```
The server will start at `http://127.0.0.1:8000`.

### Accessing the Interface
Open `index.html` directly in a web browser or access `http://127.0.0.1:8000/` once the server is running.

## Development Conventions

- **State Management**: The backend is the source of truth. It manages state in `data.json`. The frontend polls the backend every 5 seconds.
- **Trading Rules**:
  - **T+1**: Stocks bought today cannot be sold until the next trading day. Use the "T+1 Settle" button or `/api/settle` to move "today bought" volume to "available" volume.
  - **Commissions**: 0.015% (min 5 CNY).
  - **Stamp Duty**: 0.05% (applied only on sales).
- **Matching Logic**:
  - Buy orders execute if current price <= limit price.
  - Sell orders execute if current price >= limit price.
  - Stop Sell orders execute if current price <= stop price.
  - Conditional orders can be delayed using `activation_time`.

## Key Files & Scripts

- `main.py`: Core FastAPI application and matching engine.
- `index.html`: Main user interface.
- `data.json`: Current system state (account, positions, orders).
- `history.csv`: Permanent trade history.
- `bulk_buy.py`: Script to directly import positions into the account (bypasses matching).
- `bulk_stop_loss.py`: Script to batch submit stop-loss orders for all current positions.
- `system_backup.py`: CLI tool to export/import the entire system state (data + history) for backups.
- `cancel_all_orders.py`: Utility script to clear all pending orders.

## API Documentation

- `GET /api/account`: Get account summary.
- `GET /api/positions`: Get current holdings with live P&L.
- `GET /api/orders`: Get active pending orders.
- `POST /api/order`: Submit a new order.
- `POST /api/settle`: Perform T+1 end-of-day settlement.
- `POST /api/reset`: Clear all data and reset to initial state (1,000,000 CNY).

## Future Roadmap (from TODO.md)

- **Smart Strategies**: Implement 3-stage tiered take-profit strategies (automatic split orders).
- **Chart Enhancements**: Integrate K-line charts and total asset performance curves.
- **Multi-Account Support**: Allow switching between multiple virtual accounts.
- **Auto-Backup**: Scheduled automatic backups of system state.

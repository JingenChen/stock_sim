# GEMINI.md - Project Context & Instructions

This project is a minimalist **A-Share Virtual Trading System** designed for local simulation, now supporting **multiple independent accounts**.

## Project Overview

- **Purpose**: Simulates A-share trading rules using real-time market data from Sina Finance.
- **Architecture**:
  - **Backend**: Python 3.14+ with FastAPI.
  - **Frontend**: Single-page Vue 3 application (`index.html`).
- **Data Storage**:
  - `accounts/`: Root directory for all account data.
  - `accounts/{account_id}/data.json`: Account-specific balance, positions, and orders.
  - `accounts/{account_id}/history.csv`: Account-specific trade history.
  - `accounts/{account_id}/metadata.json`: Account-specific metadata (e.g., display name).
- **Core Engine**: A background thread in `main.py` iterates through all accounts in the `accounts/` directory every 3 seconds to match pending orders.

## Building and Running

### Prerequisites
- Python 3.14+
- `pip`

### Installation
```bash
pip install fastapi uvicorn requests
```

### Running the Server
```bash
python3 main.py
```

## Development Conventions

- **Multi-Account Handling**: 
  - All core trading APIs require an `X-Account-Id` header (defaults to `default`).
  - Data isolation is physically enforced by separate directories.
- **Trading Rules**: T+1 settlement, 0.015% commission (min 5 CNY), 0.05% stamp duty on sales.
- **Matching Logic**:
  - **Limit Order**: Buy if price <= limit; Sell if price >= limit; Stop Sell if price <= stop.
  - **Market Order**: Executes immediately at the current market price.
    - **Market Buy**: Backend freezes funds based on `current_price * 1.01` (1% buffer) to account for potential price fluctuations during matching.
    - **Market Sell**: Executes immediately at the latest quote.

## Key Files & Scripts

- `main.py`: Refactored to handle account directories and multi-account matching.
- `index.html`: Refactored with a tab-based account switcher and management UI.
- `accounts/`: Contains all account data.
- `bulk_buy.py`, `bulk_stop_loss.py`: (Note: These scripts currently use hardcoded endpoints and may need `X-Account-Id` header updates to target specific accounts).

## API Documentation

### Account Management
- `GET /api/accounts`: List all registered accounts.
- `POST /api/accounts`: Create a new account (returns new `id`).
- `PUT /api/accounts/{id}`: Rename an account.
- `DELETE /api/accounts/{id}`: Delete an account folder (except `default`).

### Trading (Requires `X-Account-Id` header)
- `GET /api/account`: Get active account summary.
- `GET /api/positions`: Get active holdings.
- `GET /api/orders`: Get active pending orders.
- `POST /api/order`: Submit a new order.
- `POST /api/settle`: Perform T+1 settlement.
- `POST /api/reset`: Reset active account to initial state.

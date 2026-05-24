# Multi-Account Support Implementation Plan

## 1. Backend Refactoring (main.py)

### 1.1 Data Structure & Helpers
- Change constant `DATA_FILE` and `HISTORY_FILE` to functions that return paths based on `account_id`.
- Define `ACCOUNTS_DIR = "accounts"`.
- Implement `get_account_path(account_id)` and `get_history_path(account_id)`.
- Implement `get_all_account_ids()` by listing directories in `ACCOUNTS_DIR`.

### 1.2 Account Management APIs
- `GET /api/accounts`: Returns a list of accounts with their IDs and names (stored in a `metadata.json` in each account folder).
- `POST /api/accounts`: Creates a new account folder with initial `data.json`.
- `PUT /api/accounts/{account_id}`: Updates account name in its `metadata.json`.
- `DELETE /api/accounts/{account_id}`: Removes the account folder.

### 1.3 Core API Updates
- Extract `account_id` from the `X-Account-Id` header in all endpoints.
- Update `load_data(account_id)`, `save_data(data, account_id)`, `log_history(record, account_id)`, and `get_history(account_id)`.

### 1.4 Background Matching Loop
- Modify `background_matching_loop` to:
  1. Get all account IDs.
  2. Call `trigger_matching(account_id)` for each.
  3. Sleep for a short interval between accounts or after a full cycle.

### 1.5 Migration
- On startup, check if `data.json` exists in the root. If so, move it to `accounts/default/` and create `metadata.json` with name "默认账户".

## 2. Frontend Refactoring (index.html)

### 2.1 State Management
- Add `accounts: []` and `currentAccountId: 'default'` to Vue state.
- Set up an Axios interceptor to add `headers: { 'X-Account-Id': currentAccountId }` to every request.

### 2.2 UI Updates
- Add a Tab bar at the top of the "left-col" to switch between accounts.
- Add an "Account Management" modal or section to add/edit/delete accounts.
- Ensure all components (Assets, Positions, Orders, History) refresh when `currentAccountId` changes.

## 3. Validation Strategy
- **Isolation Test**: Trade in Account A, verify Account B remains unchanged.
- **Persistence Test**: Restart server, verify all accounts are loaded correctly.
- **CRUD Test**: Add, rename, and delete an account.
- **Background Test**: Verify stop-loss orders trigger correctly in multiple accounts simultaneously.

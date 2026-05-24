import json
import os
import time
import threading
import requests
import csv
import shutil
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ACCOUNTS_DIR = "accounts"

def get_account_dir(account_id: str):
    return os.path.join(ACCOUNTS_DIR, account_id)

def get_data_file(account_id: str):
    return os.path.join(get_account_dir(account_id), "data.json")

def get_history_file(account_id: str):
    return os.path.join(get_account_dir(account_id), "history.csv")

def get_metadata_file(account_id: str):
    return os.path.join(get_account_dir(account_id), "metadata.json")

def get_asset_history_file(account_id: str):
    return os.path.join(get_account_dir(account_id), "asset_history.csv")

def calculate_total_asset(data):
    acc = data["account"]
    mv = 0.0
    for code, pos in data["positions"].items():
        q = get_stock_quote(code)
        if q:
            mv += q["price"] * pos["total_volume"]
    return acc["cash_available"] + acc["cash_frozen"] + mv

def init_system():
    if not os.path.exists(ACCOUNTS_DIR):
        os.makedirs(ACCOUNTS_DIR)
    
    # 迁移逻辑：如果根目录下有 data.json，将其迁移到 accounts/default
    old_data = "data.json"
    old_history = "history.csv"
    default_dir = get_account_dir("default")
    
    if os.path.exists(old_data) and not os.path.exists(default_dir):
        os.makedirs(default_dir)
        shutil.move(old_data, get_data_file("default"))
        if os.path.exists(old_history):
            shutil.move(old_history, get_history_file("default"))
        with open(get_metadata_file("default"), "w") as f:
            json.dump({"name": "默认账户"}, f)
    
    # 确保至少有一个默认账户
    if not os.path.exists(default_dir):
        os.makedirs(default_dir)
        initial_data = {"account": {"initial_cash": 1000000.0, "cash_available": 1000000.0, "cash_frozen": 0.0}, "positions": {}, "active_orders": []}
        with open(get_data_file("default"), "w") as f:
            json.dump(initial_data, f, indent=2)
        with open(get_metadata_file("default"), "w") as f:
            json.dump({"name": "默认账户"}, f)

def log_asset_snapshot(account_id: str):
    data = load_data(account_id)
    if not data: return
    ta = calculate_total_asset(data)
    file_path = get_asset_history_file(account_id)
    file_exists = os.path.isfile(file_path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "total_asset"])
        if not file_exists: writer.writeheader()
        writer.writerow({"date": datetime.now().strftime("%Y-%m-%d"), "total_asset": ta})

init_system()

def is_trading_time():
    now = datetime.now()
    if now.weekday() >= 5: return False
    current_time = now.strftime("%H:%M:%S")
    if "09:30:00" <= current_time <= "11:30:00": return True
    if "13:00:00" <= current_time <= "15:00:00": return True
    return False

def load_data(account_id: str):
    file_path = get_data_file(account_id)
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as f: data = json.load(f)
    except: return None
    return data

def save_data(data, account_id: str):
    file_path = get_data_file(account_id)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f: json.dump(data, f, indent=2)

def log_history(record, account_id: str):
    file_path = get_history_file(account_id)
    file_exists = os.path.isfile(file_path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "code", "name", "direction", "price", "volume", "fee", "amount"])
        if not file_exists: writer.writeheader()
        writer.writerow(record)

def get_stock_quote(code: str):
    prefix = "sh" if code.startswith("6") else "sz"
    url = f"http://hq.sinajs.cn/list={prefix}{code}"
    headers = {"Referer": "http://finance.sina.com.cn"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        content = response.text
        if '"' not in content: return None
        data_str = content.split('"')[1]
        parts = data_str.split(',')
        if len(parts) < 32: return None
        return {"name": parts[0], "prev_close": float(parts[2]), "price": float(parts[3])}
    except: return None

file_lock = threading.Lock()

def trigger_matching(account_id: str):
    if not is_trading_time(): return
    with file_lock:
        try:
            data = load_data(account_id)
            if not data or not data["active_orders"]: return
            changed = False; remaining = []
            for order in data["active_orders"]:
                if order.get("activation_time"):
                    now_str = datetime.now().strftime("%H:%M:%S")
                    if now_str < order["activation_time"]:
                        remaining.append(order)
                        continue
                
                quote = get_stock_quote(order["code"])
                if quote and quote["price"] > 0:
                    curr_price = quote["price"]
                    executed = False
                    
                    # 市价单逻辑
                    if order["direction"] == "market_buy":
                        amount = curr_price * order["volume"]
                        fee = max(5.0, amount * 0.00015)
                        total_cost = amount + fee
                        
                        # 释放冻结资金（下单时按现价+1%预冻结）
                        frozen_orig = order.get("frozen_amount", 0)
                        data["account"]["cash_frozen"] -= frozen_orig
                        data["account"]["cash_available"] += (frozen_orig - total_cost)
                        
                        pos = data["positions"].get(order["code"], {"code": order["code"], "name": order["name"], "total_volume": 0, "available_volume": 0, "cost_price": 0.0, "today_bought_volume": 0, "today_bought_cost": 0.0})
                        new_total = pos["total_volume"] + order["volume"]
                        pos["cost_price"] = (pos["cost_price"] * pos["total_volume"] + total_cost) / new_total
                        pos["total_volume"] = new_total; pos["today_bought_volume"] += order["volume"]; pos["today_bought_cost"] += total_cost
                        data["positions"][order["code"]] = pos
                        executed = True
                    elif order["direction"] == "market_sell":
                        pos = data["positions"].get(order["code"])
                        if pos and pos["total_volume"] >= order["volume"]:
                            amount = curr_price * order["volume"]
                            fee = max(5.0, amount * 0.00015) + (amount * 0.0005)
                            data["account"]["cash_available"] += (amount - fee)
                            pos["total_volume"] -= order["volume"]
                            pos["available_volume"] = max(0, pos["available_volume"] - order["volume"])
                            if pos["total_volume"] <= 0: del data["positions"][order["code"]]
                            executed = True
                        else:
                            # 持仓不足，撤单
                            changed = True; continue
                            
                    # 限价单逻辑
                    elif order["direction"] == "buy" and curr_price <= order["price"]:
                        amount = curr_price * order["volume"]
                        fee = max(5.0, amount * 0.00015)
                        total_cost = amount + fee
                        frozen_orig = order["price"] * order["volume"] + max(5.0, order["price"] * order["volume"] * 0.00015)
                        data["account"]["cash_frozen"] -= frozen_orig
                        data["account"]["cash_available"] += (frozen_orig - total_cost)
                        pos = data["positions"].get(order["code"], {"code": order["code"], "name": order["name"], "total_volume": 0, "available_volume": 0, "cost_price": 0.0, "today_bought_volume": 0, "today_bought_cost": 0.0})
                        new_total = pos["total_volume"] + order["volume"]
                        pos["cost_price"] = (pos["cost_price"] * pos["total_volume"] + total_cost) / new_total
                        pos["total_volume"] = new_total; pos["today_bought_volume"] += order["volume"]; pos["today_bought_cost"] += total_cost
                        data["positions"][order["code"]] = pos
                        executed = True
                    elif order["direction"] in ["sell", "stop_sell"]:
                        if (order["direction"] == "sell" and curr_price >= order["price"]) or (order["direction"] == "stop_sell" and curr_price <= order["price"]):
                            pos = data["positions"].get(order["code"])
                            if pos and pos["total_volume"] >= order["volume"]:
                                amount = curr_price * order["volume"]
                                fee = max(5.0, amount * 0.00015) + (amount * 0.0005)
                                data["account"]["cash_available"] += (amount - fee)
                                pos["total_volume"] -= order["volume"]
                                pos["available_volume"] = max(0, pos["available_volume"] - order["volume"])
                                if pos["total_volume"] <= 0: del data["positions"][order["code"]]
                                executed = True
                            else:
                                # 持仓不足，撤单
                                changed = True; continue
                    
                    if executed:
                        log_history({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "code": order["code"], "name": order["name"], "direction": "sell" if "sell" in order["direction"] else "buy", "price": curr_price, "volume": order["volume"], "fee": fee, "amount": amount}, account_id)
                        changed = True; continue
                remaining.append(order)
            if changed: data["active_orders"] = remaining; save_data(data, account_id)
        except Exception as e: print(f"Matching error ({account_id}): {e}")

def background_matching_loop():
    while True:
        if os.path.exists(ACCOUNTS_DIR):
            for aid in os.listdir(ACCOUNTS_DIR):
                if os.path.isdir(get_account_dir(aid)):
                    trigger_matching(aid)
        time.sleep(3)

threading.Thread(target=background_matching_loop, daemon=True).start()

# --- Account Management APIs ---

@app.get("/api/accounts")
def list_accounts():
    res = []
    if os.path.exists(ACCOUNTS_DIR):
        for aid in os.listdir(ACCOUNTS_DIR):
            meta_path = get_metadata_file(aid)
            if os.path.isfile(meta_path):
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    res.append({"id": aid, "name": meta.get("name", aid)})
    return res

class AccountCreateRequest(BaseModel):
    name: str

@app.post("/api/accounts")
def create_account(req: AccountCreateRequest):
    aid = str(int(time.time()))
    adir = get_account_dir(aid)
    os.makedirs(adir)
    initial_data = {"account": {"initial_cash": 1000000.0, "cash_available": 1000000.0, "cash_frozen": 0.0}, "positions": {}, "active_orders": []}
    with open(get_data_file(aid), "w") as f:
        json.dump(initial_data, f, indent=2)
    with open(get_metadata_file(aid), "w") as f:
        json.dump({"name": req.name}, f)
    return {"id": aid, "name": req.name}

@app.put("/api/accounts/{account_id}")
def rename_account(account_id: str, req: AccountCreateRequest):
    meta_path = get_metadata_file(account_id)
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404)
    with open(meta_path, "w") as f:
        json.dump({"name": req.name}, f)
    return {"id": account_id, "name": req.name}

@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str):
    if account_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default account")
    adir = get_account_dir(account_id)
    if os.path.exists(adir):
        shutil.rmtree(adir)
    return {"message": "ok"}

# --- Core Trading APIs ---

@app.get("/")
def read_index(): return FileResponse("index.html")

@app.get("/api/account")
def get_account(x_account_id: str = Header("default")):
    data = load_data(x_account_id)
    if not data: raise HTTPException(status_code=404)
    acc = data["account"]; mv = 0.0; dpnl = 0.0
    for code, pos in data["positions"].items():
        q = get_stock_quote(code)
        if q:
            mv += q["price"] * pos["total_volume"]
            h_vol = pos["total_volume"] - pos.get("today_bought_volume", 0)
            dpnl += (q["price"] - q["prev_close"]) * h_vol + (q["price"] * pos.get("today_bought_volume", 0)) - pos.get("today_bought_cost", 0)
    ta = acc["cash_available"] + acc["cash_frozen"] + mv
    cpnl = ta - acc["initial_cash"]
    return {"cash_available": acc["cash_available"], "cash_frozen": acc["cash_frozen"], "market_value": mv, "total_asset": ta, "daily_pnl": dpnl, "daily_pnl_rate": (dpnl/(ta-dpnl)*100 if ta!=dpnl else 0), "cumulative_pnl": cpnl, "cumulative_pnl_rate": (cpnl/acc["initial_cash"]*100 if acc["initial_cash"]!=0 else 0), "is_trading": is_trading_time()}

@app.get("/api/positions")
def get_positions(x_account_id: str = Header("default")):
    data = load_data(x_account_id)
    if not data: raise HTTPException(status_code=404)
    res = []
    for code, pos in data["positions"].items():
        q = get_stock_quote(code)
        if q:
            pos["current_price"] = q["price"]
            pos["floating_pnl"] = (q["price"] - pos["cost_price"]) * pos["total_volume"]
            pos["floating_pnl_rate"] = ((q["price"] - pos["cost_price"]) / pos["cost_price"] * 100) if pos["cost_price"]!=0 else 0
            h_vol = pos["total_volume"] - pos.get("today_bought_volume", 0)
            pos["daily_pnl"] = (q["price"] - q["prev_close"]) * h_vol + (q["price"] * pos.get("today_bought_volume", 0)) - pos.get("today_bought_cost", 0)
            pos["daily_pnl_rate"] = ((q["price"] - q["prev_close"]) / q["prev_close"] * 100) if q["prev_close"]!=0 else 0
        res.append(pos)
    return res

@app.get("/api/orders")
def get_orders(x_account_id: str = Header("default")):
    data = load_data(x_account_id)
    return data["active_orders"] if data else []

@app.get("/api/history")
def get_history(x_account_id: str = Header("default")):
    h_file = get_history_file(x_account_id)
    if not os.path.exists(h_file): return []
    try:
        with open(h_file, "r") as f:
            reader = csv.DictReader(f)
            return list(reader)[::-1]
    except: return []

@app.get("/api/asset_history")
def get_asset_history(x_account_id: str = Header("default")):
    file_path = get_asset_history_file(x_account_id)
    history = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                history = list(csv.DictReader(f))
        except: pass
    
    # 追加实时当点数据，使图表包含今日涨跌
    data = load_data(x_account_id)
    if data:
        ta = calculate_total_asset(data)
        today = datetime.now().strftime("%Y-%m-%d")
        if not history or history[-1]["date"] != today:
            history.append({"date": today, "total_asset": ta})
        else:
            history[-1]["total_asset"] = ta # 更新今日最新值
            
    return history

@app.get("/api/benchmark/{symbol}")
def get_benchmark_history(symbol: str, days: int = 250):
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={days}"
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        return [{"date": item["day"].split(" ")[0], "close": float(item["close"])} for item in data]
    except Exception as e:
        print(f"Benchmark fetch error: {e}")
        return []

@app.get("/api/quote/{code}")
def get_quote(code: str):
    q = get_stock_quote(code)
    if not q: raise HTTPException(status_code=404)
    return q

class OrderRequest(BaseModel):
    code: str; price: float; volume: int; direction: str; activation_time: Optional[str] = None

@app.post("/api/order")
def create_order(order: OrderRequest, x_account_id: str = Header("default")):
    with file_lock:
        data = load_data(x_account_id)
        if not data: raise HTTPException(status_code=404)
        q = get_stock_quote(order.code)
        if not q: raise HTTPException(status_code=404)
        
        frozen_amount = 0
        if order.direction == "buy":
            frozen_amount = order.price * order.volume + max(5.0, order.price * order.volume * 0.00015)
        elif order.direction == "market_buy":
            # 市价买：按当前价 + 1% 溢价预冻结，防止滑点
            curr_price = q["price"]
            frozen_amount = (curr_price * 1.01) * order.volume + max(5.0, (curr_price * 1.01) * order.volume * 0.00015)
        
        if frozen_amount > 0:
            if data["account"]["cash_available"] < frozen_amount: 
                raise HTTPException(status_code=400, detail=f"Insufficient funds. Need {frozen_amount:.2f}")
            data["account"]["cash_available"] -= frozen_amount; data["account"]["cash_frozen"] += frozen_amount

        if order.direction in ["sell", "stop_sell", "market_sell"]:
            pos = data["positions"].get(order.code)
            if not pos or pos["total_volume"] < order.volume: 
                raise HTTPException(status_code=400, detail="Insufficient total shares")
        
        new_order = {
            "order_id": str(int(time.time() * 1000)), 
            "timestamp": int(time.time()), 
            "code": order.code, 
            "name": q["name"], 
            "direction": order.direction, 
            "price": order.price if "market" not in order.direction else q["price"], 
            "volume": order.volume, 
            "status": "pending",
            "activation_time": order.activation_time,
            "frozen_amount": frozen_amount
        }
        data["active_orders"].append(new_order); save_data(data, x_account_id); return new_order

@app.post("/api/order/cancel/{order_id}")
def cancel_order(order_id: str, x_account_id: str = Header("default")):
    with file_lock:
        data = load_data(x_account_id)
        if not data: raise HTTPException(status_code=404)
        order_to_cancel = None; remaining = []
        for o in data["active_orders"]:
            if o["order_id"] == order_id: order_to_cancel = o
            else: remaining.append(o)
        if not order_to_cancel: raise HTTPException(status_code=404, detail="Order not found")
        
        if order_to_cancel.get("frozen_amount", 0) > 0:
            data["account"]["cash_frozen"] -= order_to_cancel["frozen_amount"]
            data["account"]["cash_available"] += order_to_cancel["frozen_amount"]
        elif order_to_cancel["direction"] == "buy": # 兼容旧版数据
            cost = order_to_cancel["price"] * order_to_cancel["volume"] + max(5.0, order_to_cancel["price"] * order_to_cancel["volume"] * 0.00015)
            data["account"]["cash_frozen"] -= cost; data["account"]["cash_available"] += cost
            
        data["active_orders"] = remaining; save_data(data, x_account_id); return {"message": "ok"}

@app.post("/api/orders/cancel_all")
def cancel_all_orders(x_account_id: str = Header("default")):
    with file_lock:
        data = load_data(x_account_id)
        if not data: raise HTTPException(status_code=404)
        for order in data["active_orders"]:
            if order.get("frozen_amount", 0) > 0:
                data["account"]["cash_frozen"] -= order["frozen_amount"]
                data["account"]["cash_available"] += order["frozen_amount"]
            elif order["direction"] == "buy": # 兼容旧版数据
                cost = order["price"] * order["volume"] + max(5.0, order["price"] * order["volume"] * 0.00015)
                data["account"]["cash_frozen"] -= cost; data["account"]["cash_available"] += cost
        data["active_orders"] = []; save_data(data, x_account_id)
        return {"message": "All orders cancelled"}

@app.post("/api/import_positions")
def import_positions(items: List[OrderRequest], x_account_id: str = Header("default")):
    with file_lock:
        data = load_data(x_account_id)
        if not data: raise HTTPException(status_code=404)
        for item in items:
            q = get_stock_quote(item.code)
            name = q["name"] if q else "未知股票"
            amount = item.price * item.volume; fee = max(5.0, amount * 0.00015); total_cost = amount + fee
            if data["account"]["cash_available"] < total_cost: continue
            data["account"]["cash_available"] -= total_cost
            pos = data["positions"].get(item.code, {"code": item.code, "name": name, "total_volume": 0, "available_volume": 0, "cost_price": 0.0, "today_bought_volume": 0, "today_bought_cost": 0.0})
            new_total = pos["total_volume"] + item.volume
            pos["cost_price"] = (pos["cost_price"] * pos["total_volume"] + total_cost) / new_total
            pos["total_volume"] = new_total; pos["available_volume"] = new_total
            data["positions"][item.code] = pos
            log_history({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "code": item.code, "name": name, "direction": "buy", "price": item.price, "volume": item.volume, "fee": fee, "amount": amount}, x_account_id)
        save_data(data, x_account_id); return {"message": "Import completed"}

@app.post("/api/settle")
def settle_t1(x_account_id: str = Header("default")):
    with file_lock:
        data = load_data(x_account_id)
        if not data: raise HTTPException(status_code=404)
        
        # 记录日终资产快照
        log_asset_snapshot(x_account_id)
        
        for c in data["positions"]: 
            pos = data["positions"][c]; pos["available_volume"] = pos["total_volume"]; pos["today_bought_volume"] = 0; pos["today_bought_cost"] = 0.0
        save_data(data, x_account_id); return {"message": "ok"}

class CashRequest(BaseModel): amount: float
@app.post("/api/deposit")
def deposit(req: CashRequest, x_account_id: str = Header("default")):
    with file_lock:
        data = load_data(x_account_id)
        if not data: raise HTTPException(status_code=404)
        data["account"]["cash_available"] += req.amount; data["account"]["initial_cash"] += req.amount
        save_data(data, x_account_id); return data["account"]

@app.post("/api/withdraw")
def withdraw(req: CashRequest, x_account_id: str = Header("default")):
    with file_lock:
        data = load_data(x_account_id)
        if not data or data["account"]["cash_available"] < req.amount: raise HTTPException(status_code=400)
        data["account"]["cash_available"] -= req.amount; data["account"]["initial_cash"] -= req.amount
        save_data(data, x_account_id); return data["account"]

@app.post("/api/reset")
def reset_data(x_account_id: str = Header("default")):
    with file_lock:
        initial_data = {"account": {"initial_cash": 1000000.0, "cash_available": 1000000.0, "cash_frozen": 0.0}, "positions": {}, "active_orders": []}
        save_data(initial_data, x_account_id)
        h_file = get_history_file(x_account_id)
        if os.path.exists(h_file): os.remove(h_file)
        return {"message": "ok"}

@app.get("/api/system/export")
def export_system_data(x_account_id: str = Header("default")):
    with file_lock:
        data = load_data(x_account_id)
        history = []
        h_file = get_history_file(x_account_id)
        if os.path.exists(h_file):
            with open(h_file, "r") as f:
                history = list(csv.DictReader(f))
        return {"data": data, "history": history}

class ImportRequest(BaseModel):
    data: dict
    history: List[dict]

@app.post("/api/system/import")
def import_system_data(req: ImportRequest, x_account_id: str = Header("default")):
    with file_lock:
        save_data(req.data, x_account_id)
        h_file = get_history_file(x_account_id)
        if req.history:
            with open(h_file, "w", newline="") as f:
                if len(req.history) > 0:
                    writer = csv.DictWriter(f, fieldnames=req.history[0].keys())
                    writer.writeheader()
                    writer.writerows(req.history)
        elif os.path.exists(h_file):
            os.remove(h_file)
        return {"message": "System data imported successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

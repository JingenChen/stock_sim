import json
import os
import time
import threading
import requests
import csv
from datetime import datetime
from fastapi import FastAPI, HTTPException
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

DATA_FILE = "data.json"
HISTORY_FILE = "history.csv"

def is_trading_time():
    now = datetime.now()
    if now.weekday() >= 5: return False
    current_time = now.strftime("%H:%M:%S")
    if "09:30:00" <= current_time <= "11:30:00": return True
    if "13:00:00" <= current_time <= "15:00:00": return True
    return False

def load_data():
    if not os.path.exists(DATA_FILE):
        initial_data = {"account": {"initial_cash": 1000000.0, "cash_available": 1000000.0, "cash_frozen": 0.0}, "positions": {}, "active_orders": []}
        save_data(initial_data); return initial_data
    try:
        with open(DATA_FILE, "r") as f: data = json.load(f)
    except: return load_data()
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

def log_history(record):
    file_exists = os.path.isfile(HISTORY_FILE)
    with open(HISTORY_FILE, "a", newline="") as f:
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

def trigger_matching():
    if not is_trading_time(): return
    with file_lock:
        try:
            data = load_data()
            if not data["active_orders"]: return
            changed = False; remaining = []
            for order in data["active_orders"]:
                # 检查条件委托：激活时间
                if order.get("activation_time"):
                    now_str = datetime.now().strftime("%H:%M:%S")
                    if now_str < order["activation_time"]:
                        remaining.append(order)
                        continue
                
                quote = get_stock_quote(order["code"])
                if quote and quote["price"] > 0:
                    curr_price = quote["price"]
                    executed = False
                    if order["direction"] == "buy" and curr_price <= order["price"]:
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
                            # 只有在成交时才真正检查持仓是否足够（应对OCO模式）
                            if pos and pos["total_volume"] >= order["volume"]:
                                amount = curr_price * order["volume"]
                                fee = max(5.0, amount * 0.00015) + (amount * 0.0005)
                                data["account"]["cash_available"] += (amount - fee)
                                pos["total_volume"] -= order["volume"]
                                # 同时也同步减少 available_volume
                                pos["available_volume"] = max(0, pos["available_volume"] - order["volume"])
                                if pos["total_volume"] <= 0: del data["positions"][order["code"]]
                                executed = True
                                
                                # OCO 逻辑：如果成交了，检查是否需要清理该股票多余的卖单
                                # 如果剩余持仓不足以支撑其他挂起的卖单，那些单子将在后续循环中因持仓不足被跳过或在此处处理
                                log_history({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "code": order["code"], "name": order["name"], "direction": "sell", "price": curr_price, "volume": order["volume"], "fee": fee, "amount": amount})
                                changed = True; continue
                            else:
                                # 持仓不足，撤单处理
                                print(f"Order cancelled due to insufficient shares: {order['code']}")
                                changed = True; continue
                    if executed:
                        log_history({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "code": order["code"], "name": order["name"], "direction": "sell" if "sell" in order["direction"] else "buy", "price": curr_price, "volume": order["volume"], "fee": fee, "amount": amount})
                        changed = True; continue
                remaining.append(order)
            if changed: data["active_orders"] = remaining; save_data(data)
        except Exception as e: print(f"Matching error: {e}")

def background_matching_loop():
    while True: trigger_matching(); time.sleep(3)

threading.Thread(target=background_matching_loop, daemon=True).start()

@app.get("/")
def read_index(): return FileResponse("index.html")

@app.get("/api/account")
def get_account():
    data = load_data(); acc = data["account"]; mv = 0.0; dpnl = 0.0
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
def get_positions():
    data = load_data(); res = []
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
def get_orders(): return load_data()["active_orders"]

@app.get("/api/history")
def get_history():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r") as f:
            reader = csv.DictReader(f)
            return list(reader)[::-1]
    except: return []

@app.get("/api/quote/{code}")
def get_quote(code: str):
    q = get_stock_quote(code)
    if not q: raise HTTPException(status_code=404)
    return q

class OrderRequest(BaseModel):
    code: str; price: float; volume: int; direction: str; activation_time: Optional[str] = None

@app.post("/api/order")
def create_order(order: OrderRequest):
    with file_lock:
        data = load_data(); q = get_stock_quote(order.code)
        if not q: raise HTTPException(status_code=404)
        if order.direction == "buy":
            cost = order.price * order.volume + max(5.0, order.price * order.volume * 0.00015)
            if data["account"]["cash_available"] < cost: raise HTTPException(status_code=400, detail="Insufficient funds")
            data["account"]["cash_available"] -= cost; data["account"]["cash_frozen"] += cost
        elif order.direction in ["sell", "stop_sell"]:
            pos = data["positions"].get(order.code)
            # OCO 支持：下单时不扣除 available_volume，只检查总持仓是否足够
            if not pos or pos["total_volume"] < order.volume: 
                raise HTTPException(status_code=400, detail="Insufficient total shares")
            # 不再执行 data["positions"][order.code]["available_volume"] -= order.volume
        new_order = {
            "order_id": str(int(time.time() * 1000)), 
            "timestamp": int(time.time()), 
            "code": order.code, 
            "name": q["name"], 
            "direction": order.direction, 
            "price": order.price, 
            "volume": order.volume, 
            "status": "pending",
            "activation_time": order.activation_time
        }
        data["active_orders"].append(new_order); save_data(data); return new_order

@app.post("/api/order/cancel/{order_id}")
def cancel_order(order_id: str):
    with file_lock:
        data = load_data()
        order_to_cancel = None; remaining = []
        for o in data["active_orders"]:
            if o["order_id"] == order_id: order_to_cancel = o
            else: remaining.append(o)
        if not order_to_cancel: raise HTTPException(status_code=404, detail="Order not found")
        if order_to_cancel["direction"] == "buy":
            cost = order_to_cancel["price"] * order_to_cancel["volume"] + max(5.0, order_to_cancel["price"] * order_to_cancel["volume"] * 0.00015)
            data["account"]["cash_frozen"] -= cost; data["account"]["cash_available"] += cost
        elif order_to_cancel["direction"] in ["sell", "stop_sell"]:
            if order_to_cancel["code"] in data["positions"]:
                data["positions"][order_to_cancel["code"]]["available_volume"] += order_to_cancel["volume"]
        data["active_orders"] = remaining; save_data(data); return {"message": "ok"}

@app.post("/api/orders/cancel_all")
def cancel_all_orders():
    with file_lock:
        data = load_data()
        for order in data["active_orders"]:
            if order["direction"] == "buy":
                cost = order["price"] * order["volume"] + max(5.0, order["price"] * order["volume"] * 0.00015)
                data["account"]["cash_frozen"] -= cost; data["account"]["cash_available"] += cost
            elif order["direction"] in ["sell", "stop_sell"]:
                if order["code"] in data["positions"]:
                    data["positions"][order["code"]]["available_volume"] += order["volume"]
        data["active_orders"] = []; save_data(data)
        return {"message": "All orders cancelled"}


@app.post("/api/import_positions")
def import_positions(items: List[OrderRequest]):
    with file_lock:
        data = load_data()
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
            log_history({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "code": item.code, "name": name, "direction": "buy", "price": item.price, "volume": item.volume, "fee": fee, "amount": amount})
        save_data(data); return {"message": "Import completed"}

@app.post("/api/settle")
def settle_t1():
    with file_lock:
        data = load_data()
        for c in data["positions"]: 
            pos = data["positions"][c]; pos["available_volume"] = pos["total_volume"]; pos["today_bought_volume"] = 0; pos["today_bought_cost"] = 0.0
        save_data(data); return {"message": "ok"}

class CashRequest(BaseModel): amount: float
@app.post("/api/deposit")
def deposit(req: CashRequest):
    with file_lock:
        data = load_data(); data["account"]["cash_available"] += req.amount; data["account"]["initial_cash"] += req.amount
        save_data(data); return data["account"]

@app.post("/api/withdraw")
def withdraw(req: CashRequest):
    with file_lock:
        data = load_data()
        if data["account"]["cash_available"] < req.amount: raise HTTPException(status_code=400)
        data["account"]["cash_available"] -= req.amount; data["account"]["initial_cash"] -= req.amount
        save_data(data); return data["account"]

@app.post("/api/reset")
def reset_data():
    with file_lock:
        initial_data = {"account": {"initial_cash": 1000000.0, "cash_available": 1000000.0, "cash_frozen": 0.0}, "positions": {}, "active_orders": []}
        save_data(initial_data)
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        return {"message": "ok"}

@app.get("/api/system/export")
def export_system_data():
    """导出系统所有数据 (data.json + history.csv)"""
    with file_lock:
        data = load_data()
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = list(csv.DictReader(f))
        return {"data": data, "history": history}

class ImportRequest(BaseModel):
    data: dict
    history: List[dict]

@app.post("/api/system/import")
def import_system_data(req: ImportRequest):
    """恢复系统数据"""
    with file_lock:
        # 保存 data.json
        save_data(req.data)
        # 恢复 history.csv
        if req.history:
            with open(HISTORY_FILE, "w", newline="") as f:
                if len(req.history) > 0:
                    writer = csv.DictWriter(f, fieldnames=req.history[0].keys())
                    writer.writeheader()
                    writer.writerows(req.history)
        elif os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        return {"message": "System data imported successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

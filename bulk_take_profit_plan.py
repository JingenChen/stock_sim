import csv
import requests
import time

BASE_URL = "http://127.0.0.1:8000/api"
PLAN_CSV = "optimized_trading_plan_advanced.csv"
GUARDIAN_CSV = "position_guardian_report.csv"
MAX_AMOUNT_PER_STOCK = 50000

def get_current_positions():
    try:
        res = requests.get(f"{BASE_URL}/positions")
        if res.status_code == 200:
            return {p["code"]: p["total_volume"] for p in res.json()}
    except:
        return {}
    return {}

def bulk_take_profit_advanced():
    print(f"💰 开始执行批量止盈逻辑 (14:50生效)...")
    current_pos = get_current_positions()
    
    # 1. 处理新计划表 optimized_trading_plan_advanced.csv
    try:
        with open(PLAN_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row["股票代码"]
                name = row["股票名称"].replace('\x00', '').strip()
                price = float(row["最新现价"])
                tp3 = float(row["三阶止盈(周线格局)"])
                
                volume = int(MAX_AMOUNT_PER_STOCK / price // 100) * 100
                if volume <= 0: continue

                # 挂14:50生效的三阶止盈单
                res = requests.post(f"{BASE_URL}/order", json={
                    "code": code, "price": tp3, "volume": volume, "direction": "sell", "activation_time": "14:50:00"
                })
                if res.status_code == 200:
                    print(f"✅ {code} {name}: 14:50止盈挂单价 {tp3}")
    except FileNotFoundError:
        print(f"⚠️ 未找到 {PLAN_CSV}")

    # 2. 处理持仓表 position_guardian_report.csv
    try:
        with open(GUARDIAN_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row["股票代码"]
                name = row["股票名称"].replace('\x00', '').strip()
                tp3 = float(row["三阶止盈(格局)"])
                
                volume = current_pos.get(code)
                if not volume: continue

                # 挂14:50生效的三阶止盈单
                res = requests.post(f"{BASE_URL}/order", json={
                    "code": code, "price": tp3, "volume": volume, "direction": "sell", "activation_time": "14:50:00"
                })
                if res.status_code == 200:
                    print(f"✅ 持仓 {code} {name}: 14:50止盈挂单价 {tp3}")
    except FileNotFoundError:
        print(f"⚠️ 未找到 {GUARDIAN_CSV}")

if __name__ == "__main__":
    bulk_take_profit_advanced()

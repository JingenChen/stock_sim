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

def bulk_stop_loss_advanced():
    print(f"🛡️ 开始执行批量止损逻辑...")
    current_pos = get_current_positions()
    
    # 1. 处理新计划表 optimized_trading_plan_advanced.csv
    try:
        with open(PLAN_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row["股票代码"]
                name = row["股票名称"].replace('\x00', '').strip()
                price = float(row["最新现价"])
                abs_stop = float(row["绝对止损(盘中)"])
                struct_stop = float(row["15m结构清仓"])
                
                volume = int(MAX_AMOUNT_PER_STOCK / price // 100) * 100
                if volume <= 0: continue

                # 挂绝对止损单
                res1 = requests.post(f"{BASE_URL}/order", json={
                    "code": code, "price": abs_stop, "volume": volume, "direction": "stop_sell"
                })
                # 挂14:50生效的15m结构止损单
                res2 = requests.post(f"{BASE_URL}/order", json={
                    "code": code, "price": struct_stop, "volume": volume, "direction": "stop_sell", "activation_time": "14:50:00"
                })
                print(f"✅ {code} {name}: 盘为止损 {abs_stop} | 14:50止损 {struct_stop}")
    except FileNotFoundError:
        print(f"⚠️ 未找到 {PLAN_CSV}")

    # 2. 处理持仓表 position_guardian_report.csv
    try:
        with open(GUARDIAN_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row["股票代码"]
                name = row["股票名称"].replace('\x00', '').strip()
                abs_stop = float(row["绝对止损(盘中)"])
                struct_stop = float(row["15m结构清仓(ZD)"])
                
                volume = current_pos.get(code)
                if not volume:
                    print(f"⏭️ 跳过 {code} {name}: 当前无持仓")
                    continue

                # 挂绝对止损单
                requests.post(f"{BASE_URL}/order", json={
                    "code": code, "price": abs_stop, "volume": volume, "direction": "stop_sell"
                })
                # 挂14:50生效的15m结构止损单
                requests.post(f"{BASE_URL}/order", json={
                    "code": code, "price": struct_stop, "volume": volume, "direction": "stop_sell", "activation_time": "14:50:00"
                })
                print(f"✅ 持仓 {code} {name}: 盘为止损 {abs_stop} | 14:50止损 {struct_stop}")
    except FileNotFoundError:
        print(f"⚠️ 未找到 {GUARDIAN_CSV}")

if __name__ == "__main__":
    bulk_stop_loss_advanced()

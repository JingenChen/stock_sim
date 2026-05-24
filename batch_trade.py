import requests
import json
import os
import math

BASE_URL = "http://127.0.0.1:8000/api"
STOCK_LIMIT = 50000  # 单只股票最大金额

# 账户映射
STRATEGIES = {
    "csi300": {
        "account_id": "1779624037",
        "name": "沪深300策略",
        "positions_file": "positions_csi300.txt",
        "signals_file": "signals_csi300.json"
    },
    "csi500": {
        "account_id": "1779624055",
        "name": "中证500策略",
        "positions_file": "positions_csi500.txt",
        "signals_file": "signals_csi500.json"
    }
}

def format_ticker(code):
    """后端代码转带前缀的代码 (如 600000 -> SH600000)"""
    if code.startswith('6'): return f"SH{code}"
    return f"SZ{code}"

def parse_ticker(prefixed_ticker):
    """带前缀的代码转后端代码 (如 SH600000 -> 600000)"""
    return prefixed_ticker[2:]

def export_positions(strategy_key):
    config = STRATEGIES[strategy_key]
    print(f"📦 正在导出 {config['name']} 的持仓...")
    headers = {"X-Account-Id": config["account_id"]}
    try:
        res = requests.get(f"{BASE_URL}/positions", headers=headers)
        if res.status_code == 200:
            positions = res.json()
            with open(config["positions_file"], "w", encoding="utf-8") as f:
                f.write(f"# 当前实盘/虚拟盘持仓清单 - {config['name']} (每日自动更新)\n")
                for pos in positions:
                    f.write(f"{format_ticker(pos['code'])}\n")
            print(f"✅ 已保存到 {config['positions_file']}")
        else:
            print(f"❌ 获取持仓失败: {res.text}")
    except Exception as e:
        print(f"💥 错误: {e}")

def execute_signals(strategy_key):
    config = STRATEGIES[strategy_key]
    if not os.path.exists(config["signals_file"]):
        print(f"⚠️ 找不到信号文件: {config['signals_file']}, 跳过执行。")
        return

    print(f"🎯 正在执行 {config['name']} 的信号...")
    headers = {"X-Account-Id": config["account_id"]}
    
    with open(config["signals_file"], "r", encoding="utf-8") as f:
        signals = json.load(f)
    
    instructions = signals.get("instructions", {})
    
    # 1. 先卖出
    for item in instructions.get("SELL", []):
        ticker = parse_ticker(item["ticker"])
        # 获取当前持仓量
        pos_res = requests.get(f"{BASE_URL}/positions", headers=headers)
        positions = pos_res.json()
        current_pos = next((p for p in positions if p["code"] == ticker), None)
        
        if current_pos and current_pos["available_volume"] > 0:
            vol = current_pos["available_volume"]
            print(f"🔻 卖出 {item['ticker']} | 数量: {vol}")
            order_payload = {
                "code": ticker,
                "price": 0, # 市价单价格可填0
                "volume": vol,
                "direction": "market_sell"
            }
            requests.post(f"{BASE_URL}/order", json=order_payload, headers=headers)
        else:
            print(f"⏩ 跳过卖出 {item['ticker']} (无可用持仓)")

    # 2. 后买入
    for item in instructions.get("BUY", []):
        ticker = parse_ticker(item["ticker"])
        # 获取当前行情以计算数量
        quote_res = requests.get(f"{BASE_URL}/quote/{ticker}")
        if quote_res.status_code != 200:
            print(f"❌ 无法获取 {item['ticker']} 行情，跳过。")
            continue
        
        quote = quote_res.json()
        price = quote["price"]
        if price <= 0: continue
        
        # 计算数量 (50000 / 价格，向下取整到100的倍数)
        volume = math.floor(STOCK_LIMIT / price / 100) * 100
        
        if volume > 0:
            print(f"🔺 买入 {item['ticker']} | 预估价: {price} | 数量: {volume}")
            order_payload = {
                "code": ticker,
                "price": 0,
                "volume": volume,
                "direction": "market_buy"
            }
            res = requests.post(f"{BASE_URL}/order", json=order_payload, headers=headers)
            if res.status_code != 200:
                print(f"❌ 买入失败: {res.text}")
        else:
            print(f"⏩ 跳过买入 {item['ticker']} (单价过高，限额不足以购买100股)")

if __name__ == "__main__":
    for key in STRATEGIES:
        export_positions(key)
        execute_signals(key)
    print("\n✨ 批量交易任务执行完毕。")

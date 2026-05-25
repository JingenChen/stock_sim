import requests
import json
import os

BASE_URL = "http://127.0.0.1:8000/api"

# 账户映射
STRATEGIES = {
    "csi300": {
        "account_id": "1779624037",
        "name": "沪深300策略",
        "positions_file": "positions_csi300.txt"
    },
    "csi500": {
        "account_id": "1779624055",
        "name": "中证500策略",
        "positions_file": "positions_csi500.txt"
    }
}

def format_ticker(code):
    """后端代码转带前缀的代码 (如 600000 -> SH600000)"""
    if code.startswith('6'): return f"SH{code}"
    return f"SZ{code}"

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

if __name__ == "__main__":
    for key in STRATEGIES:
        export_positions(key)
    print("\n✨ 持仓导出任务执行完毕。")

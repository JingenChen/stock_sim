import requests
import time

BASE_URL = "http://127.0.0.1:8000/api"

# 你的批量止损清单 (代码, 名称, 精准止损位, 数量)
stop_loss_list = [
    ("603166", "福达股份", 14.51, 4600),
    ("603663", "三祥新材", 42.58, 1500),
    ("605128", "上海沿浦", 33.71, 1900),
    ("002698", "博实股份", 14.34, 4600),
    ("601100", "恒立液压", 112.12, 500),
    ("600619", "海立股份", 17.9, 3700),
    ("300410", "正业科技", 9.99, 6500),
    ("603739", "蔚蓝生物", 14.55, 4500),
    ("600510", "黑牡丹", 9.02, 7200),
    ("300024", "机器人", 15.75, 4100),
    ("001228", "永泰运", 29.91, 2100),
    ("600551", "时代出版", 8.05, 8000),
    ("000159", "国际实业", 6.73, 9500),
    ("300992", "泰福泵业", 30.21, 2100),
    ("300475", "香农芯创", 186.9, 300)
]

def bulk_stop_loss():
    print("🛡️ 开始下达批量止损委托单...")
    for code, name, stop_price, volume in stop_loss_list:
        payload = {"code": code, "price": stop_price, "volume": volume, "direction": "stop_sell"}
        try:
            res = requests.post(f"{BASE_URL}/order", json=payload)
            if res.status_code == 200:
                print(f"✅ 止损单已挂起: {code} {name} | 触发价: {stop_price}")
            else:
                print(f"❌ 失败: {code} {name} | 原因: {res.json().get('detail')}")
        except Exception as e: print(f"💥 错误: {e}")
        time.sleep(0.05)

    print("\n🎯 所有止损单已进入委托列表。")
    print("⚠️ 提示：止损触发仅在 A 股交易时间（9:30-11:30, 13:00-15:00）生效。")

if __name__ == "__main__":
    bulk_stop_loss()

import requests

BASE_URL = "http://127.0.0.1:8000/api"

# 你的批量导入清单 (代码, 名称, 指定买入均价, 数量)
# 100万资金平均分配，每只约6.67万，最小买入单位100股
buy_list = [
    ("603166", "福达股份", 14.61, 4600),
    ("603663", "三祥新材", 42.87, 1500),
    ("605128", "上海沿浦", 34.00, 1900),
    ("002698", "博实股份", 14.48, 4600),
    ("601100", "恒立液压", 113.55, 500),
    ("600619", "海立股份", 18.14, 3700),
    ("300410", "正业科技", 10.16, 6500),
    ("603739", "蔚蓝生物", 14.81, 4500),
    ("600510", "黑牡丹", 9.23, 7200),
    ("300024", "机器人", 16.19, 4100),
    ("001228", "永泰运", 30.82, 2100),
    ("600551", "时代出版", 8.34, 8000),
    ("000159", "国际实业", 6.99, 9500),
    ("300992", "泰福泵业", 31.38, 2100),
    ("300475", "香农芯创", 194.35, 300)
]

def bulk_import():
    print(f"🚀 开始直接导入 {len(buy_list)} 只持仓股票...")
    
    # 构造请求数据，direction 统一填 "buy" 供后端复用模型
    payload = []
    for code, name, price, volume in buy_list:
        payload.append({
            "code": code,
            "price": price,
            "volume": volume,
            "direction": "buy"
        })
    
    try:
        res = requests.post(f"{BASE_URL}/import_positions", json=payload)
        if res.status_code == 200:
            print("✨ 导入成功！所有股票已直接进入持仓列表。")
            print("💰 已自动扣除相应资金及佣金 (万1.5)。")
        else:
            print(f"❌ 导入失败: {res.text}")
    except Exception as e:
        print(f"💥 连接错误: {e}")

if __name__ == "__main__":
    bulk_import()

import csv
import requests

BASE_URL = "http://127.0.0.1:8000/api"
CSV_FILE = "optimized_trading_plan_advanced.csv"
MAX_AMOUNT_PER_STOCK = 50000

def bulk_buy_advanced():
    print(f"🚀 开始读取 {CSV_FILE} 并按市价导入持仓...")
    payload = []
    
    try:
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row["股票代码"]
                name = row["股票名称"].replace('\x00', '').strip()
                price = float(row["最新现价"])
                
                # 计算最大能买入的股数，必须是100的整数倍
                volume = int(MAX_AMOUNT_PER_STOCK / price // 100) * 100
                
                if volume > 0:
                    payload.append({
                        "code": code,
                        "price": price,
                        "volume": volume,
                        "direction": "buy"
                    })
                    print(f"准备买入: {code} {name} - 现价: {price}, 数量: {volume}")
                else:
                    print(f"⚠️ 资金不足买入一手: {code} {name} (现价: {price})")
    except FileNotFoundError:
        print(f"❌ 找不到文件: {CSV_FILE}")
        return
                
    try:
        res = requests.post(f"{BASE_URL}/import_positions", json=payload)
        if res.status_code == 200:
            print("✨ 导入成功！所有股票已直接进入持仓列表。")
        else:
            print(f"❌ 导入失败: {res.text}")
    except Exception as e:
        print(f"💥 连接错误: {e}")

if __name__ == "__main__":
    bulk_buy_advanced()

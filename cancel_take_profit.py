import requests

BASE_URL = "http://127.0.0.1:8000/api"

def cancel_take_profit_orders():
    print("🧹 正在获取所有委托以筛选止盈单...")
    try:
        res = requests.get(f"{BASE_URL}/orders")
        if res.status_code != 200:
            print("❌ 无法获取委托列表")
            return
        
        orders = res.json()
        # 筛选出方向为 'sell' 的订单（bulk_take_profit_plan.py 使用的是 'sell'）
        tp_orders = [o for o in orders if o["direction"] == "sell"]
        
        if not tp_orders:
            print("✅ 当前没有挂起的止盈委托单。")
            return
        
        print(f"找到 {len(tp_orders)} 个止盈委托，准备撤销...")
        for order in tp_orders:
            oid = order["order_id"]
            name = order["name"]
            price = order["price"]
            cancel_res = requests.post(f"{BASE_URL}/order/cancel/{oid}")
            if cancel_res.status_code == 200:
                print(f"  [OK] 已撤销止盈单: {name} | 价格: {price}")
            else:
                print(f"  [Failed] 撤销失败: {name} - {cancel_res.text}")
        
        print("\n✨ 止盈委托清理完毕。")
        
    except Exception as e:
        print(f"💥 发生错误: {e}")

if __name__ == "__main__":
    cancel_take_profit_orders()

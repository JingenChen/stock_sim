import requests

BASE_URL = "http://127.0.0.1:8000/api"

def cancel_all_orders():
    print("🧹 正在获取所有挂起的委托...")
    try:
        res = requests.get(f"{BASE_URL}/orders")
        if res.status_code != 200:
            print("❌ 无法获取委托列表")
            return
        
        orders = res.json()
        if not orders:
            print("✅ 当前没有挂起的委托。")
            return
        
        print(f"找到 {len(orders)} 个委托，准备全部撤销...")
        for order in orders:
            oid = order["order_id"]
            name = order["name"]
            direction = order["direction"]
            cancel_res = requests.post(f"{BASE_URL}/order/cancel/{oid}")
            if cancel_res.status_code == 200:
                print(f"  [OK] 已撤销: {name} ({direction})")
            else:
                print(f"  [Failed] 撤销失败: {name} - {cancel_res.text}")
        
        print("\n✨ 所有委托已清理完毕，持仓已释放。")
        
    except Exception as e:
        print(f"💥 发生错误: {e}")

if __name__ == "__main__":
    cancel_all_orders()

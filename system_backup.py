import requests
import json
import argparse
import sys

BASE_URL = "http://127.0.0.1:8000/api/system"

def backup(filename):
    print(f"📦 正在备份系统数据到 {filename}...")
    try:
        res = requests.get(f"{BASE_URL}/export")
        if res.status_code == 200:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(res.json(), f, indent=2, ensure_ascii=False)
            print("✨ 备份成功！")
        else:
            print(f"❌ 备份失败: {res.text}")
    except Exception as e:
        print(f"💥 错误: {e}")

def restore(filename):
    print(f"📂 正在从 {filename} 恢复系统数据...")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            payload = json.load(f)
        
        res = requests.post(f"{BASE_URL}/import", json=payload)
        if res.status_code == 200:
            print("✨ 恢复成功！数据已更新。")
        else:
            print(f"❌ 恢复失败: {res.text}")
    except FileNotFoundError:
        print(f"❌ 找不到备份文件: {filename}")
    except Exception as e:
        print(f"💥 错误: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A股虚拟交易系统备份与还原工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", metavar="FILENAME", help="备份数据到指定文件")
    group.add_argument("--restore", metavar="FILENAME", help="从指定文件恢复数据")

    args = parser.parse_args()

    if args.backup:
        backup(args.backup)
    elif args.restore:
        restore(args.restore)

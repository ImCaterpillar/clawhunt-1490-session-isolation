# -*- coding: utf-8 -*-
"""演示：两个 Bot 的会话隔离效果（验收标准直接演示）

运行：python demo.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from session_isolator import SessionIsolator  # noqa

iso = SessionIsolator()

# 两个 Bot 各自干活，写入自己的会话
hr = iso.write(bot="hr-bot", user="u-101", kind="history",
               payload={"msg": "hr: 引导新员工完成入职", "private": True})
fin = iso.write(bot="finance-bot", user="u-202", kind="history",
                payload={"msg": "finance: 开具发票 #INV-9099", "private": True})
print("hr-bot    写入: ", hr)
print("finance-bot 写入: ", fin)
print()

# 交叉访问探测
hr_sees_fin = iso.read_with_guard("hr-bot", "u-101", "finance-bot", "u-202")
fin_sees_hr = iso.read_with_guard("finance-bot", "u-202", "hr-bot", "u-101")
print("hr-bot 读 finance-bot 的历史: ", hr_sees_fin, "（必须为空）")
print("finance-bot 读 hr-bot 的历史: ", fin_sees_hr, "（必须为空）")
print()

ok = not hr_sees_fin and not fin_sees_hr
print("=" * 40)
print("验收结果: 两 Bot 交叉访问互不可见 ->", "✅ 通过" if ok else "❌ 失败")
print("=" * 40)
print()
print("审计日志（隔离事件）:")
for a in iso.audit_log():
    print("  ", a["type"], a["requester"], "->", a["target"],
          "returned", a["returned"])
sys.exit(0 if ok else 1)
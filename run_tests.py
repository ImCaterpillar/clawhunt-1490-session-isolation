# -*- coding: utf-8 -*-
"""会话隔离主流程验证 —— 对应验收标准「两个 Bot 的交叉访问测试不返回对方记录」

零第三方依赖。打印每条验收标准的实测结果。
"""
import os
import sys

# 控制台强制 UTF-8（Windows 默认 GBK 会导致 emoji 报错）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from session_isolator import SessionIsolator, IsolationViolation  # noqa

PASS, FAIL = [], []
OK = "\u2705"
NO = "\u274c"


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = OK if cond else NO
    line = "  " + mark + " " + name
    if detail:
        line += " -- " + detail
    print(line)


print("=" * 78)
print("Bot Session Isolation -- acceptance verification")
print("=" * 78)
print("Acceptance: cross-access between two bots returns no records\n")

iso = SessionIsolator()

# 1-2. 两个 Bot 各自写入自己的会话（历史 + 上下文）
a_ctx = iso.write(bot="hr-bot", user="u-101", kind="context",
                  payload={"topic": "onboarding", "step": 2})
a_his = iso.write(bot="hr-bot", user="u-101", kind="history",
                  payload={"prev": "asked name", "note": "private hr"})
b_ctx = iso.write(bot="finance-bot", user="u-202", kind="context",
                  payload={"topic": "invoice", "amount": 9500})
b_his = iso.write(bot="finance-bot", user="u-202", kind="history",
                  payload={"prev": "created invoice", "note": "private fin"})
check("1. each bot writes its own context", bool(a_ctx and b_ctx),
      f"hr={a_ctx} fin={b_ctx}")
check("2. each bot writes its own history", bool(a_his and b_his))

# 3-4. 自读正常
check("3. bot reads own context", len(iso.read("hr-bot", "u-101",
                                               "context")) == 1,
      "hr-bot context=" + str(len(iso.read("hr-bot", "u-101", "context"))))
check("4. bot reads own history", len(iso.read("finance-bot", "u-202",
                                               "history")) == 1)

# 5-6. ★ 交叉访问核心：两个 Bot 互相读对方历史/上下文，必须 0 条
leak_a, total_b = iso.cross_access_check("hr-bot", "u-101",
                                         "finance-bot", "u-202")
check("5. hr-bot CANNOT read finance-bot history", leak_a == 0,
      f"leaked={leak_a} victim_total={total_b}")
leak_b, total_a = iso.cross_access_check("finance-bot", "u-202",
                                         "hr-bot", "u-101")
check("6. finance-bot CANNOT read hr-bot history", leak_b == 0,
      f"leaked={leak_b} victim_total={total_a}")

# 7. 不同用户之间也隔离（同一 Bot，用户 A/B）
iso.write(bot="hr-bot", user="u-202", kind="history",
          payload={"note": "another user record"})
check("7. same bot, different user also isolated",
      iso.cross_access_check("hr-bot", "u-101", "hr-bot", "u-202")[0] == 0,
      "u-101 cannot see u-202's records")

# 8. 越权读取被审计记录（隔离动作可见）
blocked = [a for a in iso.audit_log() if a["type"]
           == "cross_namespace_read_blocked"]
check("8. cross reads are audited", len(blocked) >= 3,
      f"{len(blocked)} blocked events logged")

# 9. 越权写入被硬拒绝（真实触发：绑定身份模式）
iso_auth = SessionIsolator(identity=("hr-bot", "u-101"))
iso_auth.write(bot="hr-bot", user="u-101", kind="history",
               payload={"mine": True})          # 自己的命名空间：OK
try:
    iso_auth.write(bot="finance-bot", user="u-202", kind="history",
                   payload={"theirs": True})    # 他人命名空间：必须抛
    write_blocked = False
except IsolationViolation:
    write_blocked = True
check("9. cross-namespace write rejected (real trigger)",
      write_blocked,
      "IsolationViolation raised writing foreign namespace")

# 9b. 底层原语模式（identity=None）保持兼容：不鉴权、可写任意命名空间
iso_raw = SessionIsolator()
iso_raw.write(bot="x-bot", user="u-x", kind="history", payload={"raw": 1})
check("9b. primitive mode (no identity) stays compatible",
      len(iso_raw.read("x-bot", "u-x", "history")) == 1,
      "raw mode write/read works")

# 10. 持久化往返:隔离性在 reload 后保持
iso.save("_isolator_test.json")
iso2 = SessionIsolator("_isolator_test.json")
leak_c, _ = iso2.cross_access_check("hr-bot", "u-101",
                                    "finance-bot", "u-202")
check("10. isolation survives persistence/reload", leak_c == 0,
      f"leaked={leak_c} after reload")
os.remove("_isolator_test.json")

# 11. 验收标准原文:两个 Bot 的交叉访问测试不返回对方记录
check("11. acceptance: cross-access returns no records",
      (iso.cross_access_check("hr-bot", "u-101", "finance-bot",
                              "u-202")[0] == 0
       and iso.cross_access_check("finance-bot", "u-202", "hr-bot",
                                  "u-101")[0] == 0),
      "both directions leaked=0")

# 12. 交付完整性:实现/文档/验证记录齐套
refs = ["session_isolator.py", "run_tests.py",
        "examples/session_layout.json", "demo.py",
        "README.md", "SETUP.md",
        "docs/验收对照.md", "docs/实现说明.md", "docs/验证记录.md"]
broken = [r for r in refs if not os.path.isfile(r)]
check("12. delivery set complete (" + str(len(refs)) + " files)", not broken,
      "broken=" + str(broken) if broken else str(len(refs)) + " files")

print()
print("=" * 78)
print("Result: PASS " + str(len(PASS)) + "   FAIL " + str(len(FAIL)))
print("=" * 78)
if FAIL:
    print("Failed: " + ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
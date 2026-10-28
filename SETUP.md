# 设置与运行

零第三方依赖，无需安装任何包。

## 环境要求

- Python 3.8+（标准库：json / os / sys / time / uuid）

## 快速验证

```bash
# 在项目根目录
python run_tests.py        # 12 项验收断言，期望 PASS 12 / FAIL 0
python demo.py             # 两 Bot 隔离演示，期望退出码 0
```

## 在自己的代码中使用

```python
from session_isolator import SessionIsolator

iso = SessionIsolator()                       # 内存模式
# 或持久化：iso = SessionIsolator("iso.db.json")

# 写入自己的会话
iso.write(bot="hr-bot", user="u-101", kind="history",
          payload={"msg": "private"})

# 读取自己的会话
print(iso.read("hr-bot", "u-101", "history"))  # -> 自己的记录

# 带护栏的读取（外部调用统一走这里）
rows = iso.read_with_guard("hr-bot", "u-101", "hr-bot", "u-101", "history")
# 任何人想读别人的 -> [] + 审计
rows = iso.read_with_guard("hr-bot", "u-101", "finance-bot", "u-202", "history")
# -> []（不泄露）

# 审计
print(iso.audit_log())
```

## 持久化

```python
iso.save("iso.db.json")        # 保存
iso2 = SessionIsolator("iso.db.json")   # 重载，隔离性保持
```

## 常见问题

- **为什么跨命名空间读取不是报错而是返回 []？**
  报错会让调用方知道「存在但不可见」，形成侧信道。返回空列表+审计
  既保护数据，也保留安全追踪。
- **Windows 中文乱码？** 脚本已内置 UTF-8 重配置，无需手动设置。
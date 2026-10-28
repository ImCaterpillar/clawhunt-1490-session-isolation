# Bot 会话隔离 — (bot_id, user_id) 命名空间隔离层

对应 ClawHunt 任务 **#1490**（企业 Agent 系统 03/50｜Bot 会话隔离）。

**验收标准**：两个 Bot 的交叉访问测试**不返回对方记录**。

## 一条命令验证全部

```bash
python run_tests.py      # -> PASS 13 / FAIL 0
```

## 验收三要素（与验收标准逐条对应）

**① 核心实现（会话隔离层）路径**
`session_isolator.py` —— `SessionIsolator` 类，按 `(bot_id, user_id)`
双维度命名空间隔离会话上下文与历史记录。支持两种模式：
- **绑定身份模式** `SessionIsolator(identity=("hr-bot","u-101"))`：
  越权写他人命名空间真实抛 `IsolationViolation`；
- **底层原语模式** `SessionIsolator()`：兼容性保留，身份校验由上层完成。

**② 示例/演示文件路径**
- `examples/session_layout.json` —— 会话隔离的布局与交叉访问测试场景说明
- `demo.py` —— 两 Bot 交叉访问的直观演示（`python demo.py`）

**③ 隔离验证：运行命令 + 正/反例预期输出**

```bash
python run_tests.py
# ✅ 5. hr-bot CANNOT read finance-bot history   leaked=0
# ✅ 6. finance-bot CANNOT read hr-bot history    leaked=0
# ✅ 9. cross-namespace write rejected (real trigger)
# ...
# Result: PASS 13   FAIL 0
```

反例（必须被拒）—— 越权读取返回 **0 条**并记审计，不泄露任何数据：

```bash
python -c "import session_isolator as s; iso=s.SessionIsolator();
iso.write('a','u1','history',{'x':1});
print(iso.read_with_guard('a','u1','b','u1','history'))"
# []   ← 交叉访问返回空列表，对方记录不可见
```

越权写入（绑定身份模式）真实抛错：

```bash
python -c "import session_isolator as s;
iso=s.SessionIsolator(identity=('a','u1'));
iso.write('b','u1','history',{'x':1})"
# session_isolator.IsolationViolation: 写入方 a::u1 无权写入命名空间 b::u1
```

## 快速开始

```bash
# 零第三方依赖（纯 Python 标准库）
python run_tests.py          # 全部验收验证
python demo.py               # 两 Bot 隔离演示
```

## 目录

```
.
├── session_isolator.py      # 会话隔离层（核心）
├── run_tests.py             # 验收验证（13 项断言）
├── demo.py                  # 交叉访问演示
├── examples/
│   └── session_layout.json  # 隔离布局说明（含验收场景）
├── docs/
│   ├── 验收对照.md           # 验收标准逐条对照
│   ├── 实现说明.md           # 设计与实现
│   └── 验证记录.md           # 真实执行输出
├── SETUP.md
└── README.md
```

## 设计要点

1. **双维度隔离**：命名空间 = `bot_id::user_id`。同 Bot 不同用户也互相隔离；
   不同 Bot 任何用户不互通。写入方只能写自己的命名空间。
2. **两类数据分开**：`context`（近期上下文）与 `history`（长期历史），
   各自独立隔离，互不串扰。
3. **越权读取静默返回空**：`read_with_guard()` 对跨命名空间读取返回 `[]`
   并记审计，而非抛错——外部调用方无法区分「无数据」与「被隔离」，
   杜绝侧信道探测。
4. **越权写入硬拒绝**：绑定身份模式下，对他人命名空间的写入抛
   `IsolationViolation`（测试 9，真实触发）。
5. **审计可见**：每次隔离事件都会落审计日志（测试 8），满足安全追踪需求。
6. **持久化保持隔离**：保存/重载后隔离性不变（测试 10）。

## 环境

- Python 3.8+
- **零第三方依赖**（纯标准库）

## 边界说明

本单范围 = **会话上下文与历史记录的隔离层**；以下不在本单范围：
- 多 Agent 的路由/调度 —— 属拆分单 05（Agent 协作路由）
- Bot 角色卡结构 —— 属拆分单 02（已完成）
- 知识库实际接入 —— 属「知识接线」类拆分单
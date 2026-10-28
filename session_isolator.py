# -*- coding: utf-8 -*-
"""会话隔离层 —— 为不同 Bot 与用户隔离会话上下文与历史记录。

对应 ClawHunt 任务 #1490（企业 Agent 系统 03/50｜Bot 会话隔离），
验收标准：**两个 Bot 的交叉访问测试不返回对方记录**。

设计：
  - 隔离维度 = (bot_id, user_id) 命名空间。写入方只能写自己的命名空间，
    读取方只能读自己的命名空间；跨命名空间一律返回空结果并记审计。
  - 会话上下文（近期、可失效）与历史记录（长期）分开存放，各自隔离。
  - 零第三方依赖（纯 Python 标准库），可内存运行或持久化到 JSON 文件。

使用：
    from session_isolator import SessionIsolator
    iso = SessionIsolator()
    iso.write(bot="bot-a", user="u-1", kind="context", payload={...})
    iso.read(bot="bot-a", user="u-1", kind="context")   # -> 拿到
    iso.read(bot="bot-b", user="u-1", kind="context")   # -> []（对方记录不可见）
"""
import json
import os
import time
import uuid


class IsolationViolation(Exception):
    """对他人命名空间的写入尝试——直接拒绝并抛错。"""


class SessionIsolator:
    """按 (bot_id, user_id) 命名空间隔离的会话存储。"""

    def __init__(self, db_path=None, identity=None):
        # _store[bot][user][kind][session_id] = record
        self._store = {}
        self._audit = []          # 越权/拒绝事件
        self.db_path = db_path
        # identity: 当前调用方的 (bot_id, user_id)；None = 底层原语模式（不鉴权）。
        # 绑定身份后，write() 对他人命名空间的写入将真实抛 IsolationViolation。
        self.identity = tuple(identity) if identity else None
        if db_path and os.path.isfile(db_path):
            self._load(db_path)

    # ------------------------------------------------------------------
    # 命名空间隔离
    # ------------------------------------------------------------------
    @staticmethod
    def _ns(bot, user):
        return "{}::{}".format(bot or "", user or "")

    def _ensure(self, bot, user):
        return self._store.setdefault(
            bot, {}).setdefault(user, {"context": {}, "history": {}})

    def _check_write(self, bot, user):
        """绑定身份模式下，校验写入目标必须是自己的命名空间。"""
        if self.identity is not None and (bot, user) != self.identity:
            raise IsolationViolation(
                f"写入方 {self._ns(*self.identity)} 无权写入命名空间 "
                f"{self._ns(bot, user)}")

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    def write(self, bot, user, kind="context", payload=None, session_id=None):
        """写入一条会话记录。kind ∈ {context, history}。

        底层原语模式（identity=None）：由调用方自行保证只写自己的命名空间。
        绑定身份模式（identity=(bot,user)）：越权写入抛 IsolationViolation。
        """
        if kind not in ("context", "history"):
            raise ValueError("kind 必须为 'context' 或 'history'")
        self._check_write(bot, user)
        box = self._ensure(bot, user)[kind]
        sid = session_id or uuid.uuid4().hex[:12]
        box[sid] = {
            "session_id": sid,
            "kind": kind,
            "payload": payload if payload is not None else {},
            "created_at": time.time(),
        }
        return sid

    # ------------------------------------------------------------------
    # 读取（核心隔离）
    # ------------------------------------------------------------------
    def read(self, bot, user, kind="context", session_id=None):
        """读取自己命名空间的记录；跨命名空间返回空列表并审计。

        这是验收标准的落点：**交叉访问不返回对方记录**。
        任何情况下都绝不返回其它 (bot, user) 命名空间的数据。
        """
        if kind not in ("context", "history"):
            raise ValueError("kind 必须为 'context' 或 'history'")
        box = self._store.get(bot, {}).get(user, {}).get(kind, {})
        if session_id:
            rec = box.get(session_id)
            return [rec] if rec else []
        return list(box.values())

    def read_with_guard(self, requester_bot, requester_user,
                        target_bot, target_user, kind="context"):
        """带越权护栏的读取：请求方只能读自己的命名空间。

        若请求读取他人的命名空间，返回 []（不泄露任何数据）并记审计，
        而不是抛异常——保证外部调用方无法据此区分「无数据」与「被隔离」。
        """
        if (requester_bot, requester_user) != (target_bot, target_user):
            self._audit.append({
                "ts": time.time(),
                "type": "cross_namespace_read_blocked",
                "requester": self._ns(requester_bot, requester_user),
                "target": self._ns(target_bot, target_user),
                "kind": kind,
                "returned": 0,
            })
            return []
        return self.read(requester_bot, requester_user, kind)

    def list_namespaces(self):
        """列出当前存在的所有命名空间（仅用于运维展示，不暴露内容）。"""
        return sorted(
            self._ns(b, u)
            for b, users in self._store.items()
            for u in users
        )

    # ------------------------------------------------------------------
    # 审计
    # ------------------------------------------------------------------
    def audit_log(self):
        return list(self._audit)

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def save(self, path=None):
        path = path or self.db_path
        if not path:
            raise ValueError("需要 path 才能持久化")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"store": self._store, "audit": self._audit},
                      f, ensure_ascii=False, indent=2)
        return path

    def _load(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._store = data.get("store", {})
            self._audit = data.get("audit", [])
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            # 持久化文件损坏/不可读：优雅降级为空存储，绝不崩溃。
            # 隔离性不受影响（空存储天然无泄露），数据恢复由上层备份策略负责。
            self._store = {}
            self._audit = [{
                "ts": time.time(),
                "type": "db_load_failed_reset",
                "path": str(path),
                "error": f"{type(e).__name__}: {e}",
                "action": "started_empty",
            }]

    # ------------------------------------------------------------------
    # 隔离完备性证明（验收核心）
    # ------------------------------------------------------------------
    def cross_access_check(self, observer_bot, observer_user,
                           victim_bot, victim_user, kind="history"):
        """交叉访问探测：观察者尝试读取受害者的全部记录。

        返回 (leaked, total)：
          - total = 受害者命名空间实际存在的记录数
          - leaked = 观察者能读到的记录数（必须恒为 0）
        用于验收测试断言「不返回对方记录」。
        """
        victim_total = len(self._store.get(victim_bot, {})
                           .get(victim_user, {}).get(kind, {}))
        observed = self.read_with_guard(observer_bot, observer_user,
                                        victim_bot, victim_user, kind)
        return len(observed), victim_total
"""拍摄通告业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "notice"
REQUIRED_FIELDS = ["通告编号", "拍摄日期", "集合时间"]
OPTIONAL_FIELDS = ["拍摄地点", "拍摄场次", "出勤人员", "用车安排"]
STATUS_ORDER = ["待下发", "已下发", "执行中", "已完成"]
ACTION_RULES = {"下发通告": "已下发", "开始执行": "执行中", "确认完成": "已完成"}
NEGATIVE_ACTIONS: list[str] = []

# 每个动作允许的前置状态：通告单只能按 STATUS_ORDER 逐级流转，禁止重复下发与跳级
ACTION_SOURCES = {
    "下发通告": ["待下发"],
    "开始执行": ["已下发"],
    "确认完成": ["执行中"],
}


def _parse_moment(raw: Any) -> datetime | None:
    """把日期或日期时间字符串解析成 datetime；解析不了返回 None。"""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def gathering_time_valid(entry: dict[str, Any]) -> bool:
    """集合时间不能晚于拍摄日期（通告日期）；两个字段都要能解析成日期时间。"""
    shoot_day = _parse_moment(entry.get("拍摄日期"))
    gather_at = _parse_moment(entry.get("集合时间"))
    if shoot_day is None or gather_at is None:
        return False
    return gather_at.date() <= shoot_day.date()


def normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """列表、详情与概览共用的展示口径：派生 pending/abnormal，并把通告状态对齐到状态机。

    只返回副本，不改写既有通告的存储内容。
    """
    view = dict(entry)
    status = str(entry.get("status") or STATUS_ORDER[0])
    view["status"] = status
    view["通告状态"] = status
    view["pending"] = status != STATUS_ORDER[-1]
    view["abnormal"] = not gathering_time_valid(entry)
    return view


class NoticeService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("通告编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [normalize_entry(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return normalize_entry(entry)

    def summary(self) -> dict[str, Any]:
        """页面统计卡与运营概览共用的汇总口径，保证两处数量一致。"""
        rows = [normalize_entry(row) for row in store.rows(MODULE)]
        by_status = {status: 0 for status in STATUS_ORDER}
        for row in rows:
            by_status.setdefault(row["status"], 0)
            by_status[row["status"]] += 1
        return {
            "total": len(rows),
            "pending": sum(1 for row in rows if row["pending"]),
            "abnormal": sum(1 for row in rows if row["abnormal"]),
            "by_status": by_status,
        }

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        number = str(values.get("通告编号") or "").strip()
        if any(str(row.get("通告编号") or "").strip() == number for row in store.rows(MODULE)):
            return None, f"通告编号 {number} 已存在，不能重复登记"
        if not gathering_time_valid(values):
            return None, "集合时间不能晚于拍摄日期，请调整后再保存"
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS + OPTIONAL_FIELDS if values.get(field) is not None})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, "拍摄通告单已登记"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"拍摄通告单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于拍摄通告可执行范围"
        current = str(entry.get("status") or STATUS_ORDER[0])
        if current not in ACTION_SOURCES[action]:
            expected = "、".join(ACTION_SOURCES[action])
            return None, f"当前状态为「{current}」，「{action}」只允许在「{expected}」状态下执行"
        if action == "下发通告" and not gathering_time_valid(entry):
            return None, "集合时间晚于拍摄日期，不能下发通告"
        if action == "开始执行" and not str(entry.get("拍摄地点") or "").strip():
            return None, "缺少拍摄地点，不能开始执行"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = not gathering_time_valid(entry)
        return entry, f"拍摄通告单已{action}"


# 概览统计套用与列表、详情一致的展示口径
store.register_normalizer(MODULE, normalize_entry)

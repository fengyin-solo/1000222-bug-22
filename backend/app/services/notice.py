"""拍摄通告业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from app.store import store

MODULE = "notice"
REQUIRED_FIELDS = ["通告编号", "拍摄日期", "集合时间"]
ENTRY_FIELDS = ["通告编号", "拍摄日期", "集合时间", "拍摄地点", "拍摄场次", "出勤人员", "用车安排"]
STATUS_ORDER = ["待下发", "已下发", "执行中", "已完成"]
ACTION_RULES = {"下发通告": "已下发", "开始执行": "执行中", "确认完成": "已完成"}
NEGATIVE_ACTIONS = []
# 进入「执行中」前必须已经填写的字段
EXECUTION_REQUIRED_FIELDS = ["拍摄地点"]
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def _parse_moment(raw: object) -> datetime | None:
    """把页面/接口传来的日期时间统一解析成 datetime；解析不了返回 None。"""
    text = str(raw or "").strip()
    if not text:
        return None
    text = text.replace("T", " ").replace("/", "-")
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def datetime_rule_violated(row: Mapping[str, Any]) -> bool:
    """集合时间晚于拍摄日期（通告日期）即违反日期时间条件。

    日期或时间缺省时交给必填校验兜底，这里不判；有值但解析不出同样视为不符合规则。
    列表、详情、概览都走这一个口径。
    """
    shoot_raw = str(row.get("拍摄日期") or "").strip()
    assembly_raw = str(row.get("集合时间") or "").strip()
    if not shoot_raw or not assembly_raw:
        return False
    shoot_day = _parse_moment(shoot_raw)
    assembly_at = _parse_moment(assembly_raw)
    if shoot_day is None or assembly_at is None:
        return True
    return assembly_at.date() > shoot_day.date()


def normalize_notice_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """按统一状态标准派生展示用标记：异常 = 已记录的异常 或 违反日期时间条件。

    返回副本，不改写已存储的通告数据，既有通告保持原样。
    """
    normalized = dict(row)
    normalized["abnormal"] = bool(row.get("abnormal")) or datetime_rule_violated(row)
    return normalized


def _datetime_check(values: Mapping[str, Any]) -> str | None:
    """保存前的日期时间条件校验；通过返回 None，否则返回拒绝原因。"""
    shoot_day = _parse_moment(values.get("拍摄日期"))
    assembly_at = _parse_moment(values.get("集合时间"))
    if shoot_day is None or assembly_at is None:
        return "拍摄日期或集合时间格式不正确（示例：2026-09-26、2026-09-26 08:00）"
    if assembly_at.date() > shoot_day.date():
        return "集合时间不能晚于拍摄日期"
    return None


class NoticeService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        shoot_date: str | None = None,
        assembly_time: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [normalize_notice_row(row) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("通告编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if shoot_date:
            rows = [row for row in rows if shoot_date in str(row.get("拍摄日期", ""))]
        if assembly_time:
            rows = [row for row in rows if assembly_time in str(row.get("集合时间", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return normalize_notice_row(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{'、'.join(missing)}"]
        notice_no = str(values.get("通告编号") or "").strip()
        rows = store.rows(MODULE)
        if any(str(row.get("通告编号") or "").strip() == notice_no for row in rows):
            return None, [f"通告编号 {notice_no} 已存在，不允许重复登记"]
        datetime_error = _datetime_check(values)
        if datetime_error:
            return None, [datetime_error]
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in ENTRY_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"拍摄通告单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于拍摄通告可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        expected = STATUS_ORDER[STATUS_ORDER.index(target) - 1]
        current = str(entry.get("status") or "")
        if current != expected:
            return None, f"拍摄通告单当前状态为「{current}」，「{action}」仅可在「{expected}」状态执行"
        if action in ("下发通告", "开始执行") and datetime_rule_violated(entry):
            return None, f"集合时间晚于拍摄日期或时间格式不正确，不符合规则，不允许{action}"
        if target == "执行中":
            missing = [field for field in EXECUTION_REQUIRED_FIELDS if not str(entry.get(field) or "").strip()]
            if missing:
                return None, f"缺少{'、'.join(missing)}，不允许进入执行中"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = bool(entry.get("abnormal")) or action in NEGATIVE_ACTIONS
        return entry, f"拍摄通告单已{action}"


# 概览看板与列表、详情共用同一套状态标准；派生只读副本，不改写既有通告。
store.register_normalizer(MODULE, normalize_notice_row)

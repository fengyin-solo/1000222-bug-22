"""拍摄通告接口：维护拍摄通告单，覆盖下发通告、开始执行、确认完成等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.notice import NoticeService

router = APIRouter(prefix="/api/notice", tags=["拍摄通告"])

service = NoticeService()

LIST_FIELDS = ["通告编号", "拍摄日期", "集合时间", "拍摄地点", "拍摄场次", "出勤人员", "用车安排", "通告状态"]
STATUSES = ["待下发", "已下发", "执行中", "已完成"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按通告编号检索"),
    status: str | None = Query(default=None, description="待下发、已下发、执行中、已完成"),
    shoot_date: str | None = Query(default=None, description="按拍摄日期检索"),
    assembly_time: str | None = Query(default=None, description="按集合时间检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按通告编号、状态与日期时间条件过滤拍摄通告列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword,
        status=status,
        shoot_date=shoot_date,
        assembly_time=assembly_time,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出拍摄通告清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "notice", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条拍摄通告单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"拍摄通告单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条拍摄通告单，缺字段或不符合日期时间规则时说明原因而不是静默丢弃。"""
    entry, errors = service.create_entry(payload.values)
    if errors:
        return ActionResult(ok=False, message="；".join(errors))
    return ActionResult(ok=True, message="拍摄通告单已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条拍摄通告单执行下发通告、开始执行、确认完成；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

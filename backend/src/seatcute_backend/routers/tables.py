from typing import List

from fastapi import APIRouter, Depends

from ..deps import get_store
from ..schemas import ErrorResponse, SeatFromQueueRequest, Table, TableView
from ..store import MockStore

router = APIRouter(prefix="/tables", tags=["Tables"])

_TABLE_ERROR_RESPONSES = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
}


@router.get("", response_model=List[TableView])
def list_tables(store: MockStore = Depends(get_store)) -> list:
    return store.list_tables()


@router.post(
    "/{table_id}/seat-from-queue",
    response_model=Table,
    responses=_TABLE_ERROR_RESPONSES,
)
def seat_from_queue(
    table_id: str, body: SeatFromQueueRequest, store: MockStore = Depends(get_store)
) -> dict:
    return store.seat_from_queue(table_id, body.queue_entry_id)


@router.post(
    "/{table_id}/seat-bypass",
    response_model=Table,
    responses=_TABLE_ERROR_RESPONSES,
)
def seat_bypass(table_id: str, store: MockStore = Depends(get_store)) -> dict:
    return store.seat_bypass(table_id)


@router.post(
    "/{table_id}/release",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
def release_table(table_id: str, store: MockStore = Depends(get_store)) -> None:
    store.release_table(table_id)

from fastapi import APIRouter, Depends

from ..deps import get_store
from ..schemas import AdminConfig, AdminConfigInput
from ..store import MockStore

router = APIRouter(tags=["Config"])


@router.get("/config", response_model=AdminConfig)
def get_config(store: MockStore = Depends(get_store)) -> dict:
    return store.get_config()


@router.put("/config", response_model=AdminConfig)
def save_config(body: AdminConfigInput, store: MockStore = Depends(get_store)) -> dict:
    counts = {int(k): v for k, v in body.counts.items()}
    turnover = {int(k): v for k, v in body.turnover.items()}
    return store.save_config(counts, turnover)

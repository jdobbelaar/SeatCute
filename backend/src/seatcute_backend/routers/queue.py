from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ..deps import get_store
from ..errors import InvalidQueryError, NotFoundError
from ..schemas import ErrorResponse, JoinQueueRequest, QueueEntry, QueueEntryView, WaitEstimate
from ..store import SIZES, MockStore

router = APIRouter(tags=["Queue"])


@router.get("/queue", response_model=List[QueueEntryView])
def list_queue(
    size: Optional[int] = Query(None, description="Restrict to one size's queue; omit for all sizes."),
    store: MockStore = Depends(get_store),
) -> list:
    # NOTE: validated manually (rather than via `Literal[1, 2, 4, 6]` on the
    # query param) because query-string ints aren't coerced before Literal
    # membership is checked in fastapi==0.141.1 / pydantic==2.13.5, so a
    # perfectly valid `?size=2` was rejected as a literal_error. Tracked as a
    # library quirk to revisit on a future upgrade.
    if size is not None and size not in SIZES:
        raise InvalidQueryError(f"size must be one of {list(SIZES)}.")
    return store.list_queue(size)


@router.post(
    "/queue",
    response_model=QueueEntry,
    status_code=201,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def join_queue(body: JoinQueueRequest, store: MockStore = Depends(get_store)) -> dict:
    return store.join_queue(body.name, body.phone, body.party_size)


@router.get("/queue/wait-estimate", response_model=WaitEstimate)
def get_wait_estimate(
    party_size: int = Query(..., alias="partySize", ge=1, description="Exact party size entered by the customer."),
    store: MockStore = Depends(get_store),
) -> dict:
    return store.get_wait_estimate(party_size)


@router.get(
    "/reservation-status",
    response_model=QueueEntryView,
    responses={404: {"model": ErrorResponse}},
)
def find_active_queue_entry_by_phone(
    phone: str = Query(..., description="Phone number as entered by the customer (not normalized)."),
    store: MockStore = Depends(get_store),
) -> dict:
    result = store.find_active_queue_entry_by_phone(phone)
    if result is None:
        raise NotFoundError("No active reservation found for this phone number.")
    return result


@router.delete(
    "/queue/{queue_entry_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
def cancel_queue_entry(queue_entry_id: str, store: MockStore = Depends(get_store)) -> None:
    store.cancel_queue_entry(queue_entry_id)


@router.post(
    "/queue/{queue_entry_id}/dismiss",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
def dismiss_queue_entry(queue_entry_id: str, store: MockStore = Depends(get_store)) -> None:
    store.dismiss_queue_entry(queue_entry_id)

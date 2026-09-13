"""Pydantic models mirroring openapi.yaml's components/schemas.

Python fields are snake_case; alias_generator=to_camel makes the wire
format (request/response JSON) match openapi.yaml exactly (camelCase).
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

TableSize = Literal[1, 2, 4, 6]
_SIZE_KEYS = {"1", "2", "4", "6"}


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _validate_size_map(value: Dict[str, int], *, min_value: int) -> Dict[str, int]:
    if set(value.keys()) != _SIZE_KEYS:
        raise ValueError(f'must have exactly these keys: {sorted(_SIZE_KEYS)}')
    for v in value.values():
        if not isinstance(v, int) or isinstance(v, bool) or v < min_value:
            raise ValueError(f"values must be integers >= {min_value}")
    return value


class AdminConfigInput(CamelModel):
    counts: Dict[str, int]
    turnover: Dict[str, int]

    @field_validator("counts")
    @classmethod
    def _check_counts(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_size_map(v, min_value=0)

    @field_validator("turnover")
    @classmethod
    def _check_turnover(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_size_map(v, min_value=1)


class AdminConfig(AdminConfigInput):
    sizes: List[TableSize] = [1, 2, 4, 6]


class Party(CamelModel):
    name: str
    phone: str


class Table(CamelModel):
    id: str
    size: TableSize
    label: str
    status: Literal["available", "occupied"]
    occupied_at: Optional[int] = None
    party: Optional[Party] = None
    pending_removal: bool


class TableView(Table):
    elapsed_minutes: Optional[int] = None
    free_at: int


class QueueEntry(CamelModel):
    id: str
    name: str
    phone: str
    party_size: int
    queue_size: TableSize
    joined_at: int


class QueueEntryView(QueueEntry):
    position: int
    projected_at: Optional[int] = None
    projected_wait_ms: Optional[int] = None


class JoinQueueRequest(CamelModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    party_size: int = Field(ge=1)


class SeatFromQueueRequest(CamelModel):
    queue_entry_id: str


class WaitEstimate(CamelModel):
    queue_size: Optional[TableSize] = None
    immediate: bool
    projected_at: Optional[int] = None
    projected_wait_ms: Optional[int] = None


class ErrorResponse(BaseModel):
    code: str
    message: str

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    """Consistent {data, msg} envelope for new endpoints (Users, Departments,
    Priorities, /ticket-new, /all-tickets).

    Existing endpoints predate this convention and keep their bare response
    shape - this is not retrofitted onto them, per the "don't rewrite older
    endpoints unless needed" instruction.
    """

    data: T
    msg: str

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_inventory_transaction_service, require_roles
from app.models.enums import InventoryTransactionType
from app.models.user import User
from app.schemas.inventory_transaction import InventoryTransactionResponse
from app.schemas.response import DataResponse
from app.services.inventory_transaction_service import InventoryTransactionService

router = APIRouter(prefix="/inventory-transactions", tags=["Inventory Transactions"])

# Company-wide feed, not scoped to one item - a step up in scope from
# "history of one item I can already see" (GET /inventory-items/{id}/
# transactions, which Technician can also reach), so this one endpoint is
# Company Administrator only.
_VIEW_ROLES = ("Company Administrator",)


@router.get("", response_model=DataResponse[list[InventoryTransactionResponse]])
def list_inventory_transactions(
    inventory_item_id: int | None = Query(default=None),
    ticket_id: int | None = Query(default=None),
    transaction_type: InventoryTransactionType | None = Query(default=None),
    performed_by_user_id: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    inventory_transaction_service: InventoryTransactionService = Depends(
        get_inventory_transaction_service
    ),
    _current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> DataResponse[list[InventoryTransactionResponse]]:
    transactions, total = inventory_transaction_service.list_company_transactions(
        inventory_item_id=inventory_item_id,
        ticket_id=ticket_id,
        transaction_type=transaction_type,
        performed_by_user_id=performed_by_user_id,
        skip=skip,
        limit=limit,
    )
    return DataResponse(
        data=[InventoryTransactionResponse.model_validate(t) for t in transactions],
        msg=f"Fetched {len(transactions)} of {total} inventory transactions",
    )

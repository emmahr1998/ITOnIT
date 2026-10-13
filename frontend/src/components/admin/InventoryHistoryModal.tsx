import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchInventoryItemTransactions } from "../../api/inventoryTransactions";
import { getApiErrorMessage } from "../../api/client";
import { Modal } from "../common/Modal";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { ErrorMessage } from "../common/ErrorMessage";
import { EmptyState } from "../common/EmptyState";
import { InventoryTransactionTypeBadge } from "../common/InventoryTransactionTypeBadge";
import { formatEnumLabel } from "../../utils/formatEnumLabel";
import type { InventoryItem } from "../../types/inventoryItem";
import type {
  InventoryTransaction,
  InventoryTransactionType,
} from "../../types/inventoryTransaction";
import styles from "./InventoryHistoryModal.module.css";

// Every field_name recorded by InventoryTransactionService.record() (see
// InventoryItemService._record_update_transactions and the dedicated
// status/holder/location/stock transaction types) - falls back to a
// title-cased version of the raw field name for anything not listed here.
const FIELD_LABELS: Record<string, string> = {
  inventory_category_id: "Category",
  current_location_id: "Location",
  current_holder_user_id: "Holder",
  status: "Status",
  stock_quantity: "Stock Quantity",
  name: "Name",
  manufacturer: "Manufacturer",
  model: "Model",
  serial_number: "Serial Number",
  asset_tag: "Asset Tag",
  condition: "Condition",
  minimum_stock: "Minimum Stock",
  purchase_date: "Purchase Date",
  warranty_expiration: "Warranty Expiration",
  supplier: "Supplier",
  purchase_cost: "Purchase Cost",
  invoice_number: "Invoice Number",
  image_path: "Image",
  notes: "Notes",
};

// Fallback summary for transactions that carry no field_name (e.g. CREATED,
// and the BULK-quantity-only paths through reserve/release/consume/undo).
const ACTION_SUMMARY: Record<InventoryTransactionType, string> = {
  CREATED: "Item created",
  EDITED: "Item edited",
  STOCK_ADJUSTED: "Stock adjusted",
  STATUS_CHANGED: "Status changed",
  HOLDER_CHANGED: "Holder changed",
  LOCATION_CHANGED: "Location changed",
  RESERVED: "Reserved for ticket",
  RELEASED: "Reservation released",
  CONSUMED: "Consumed",
  CONSUME_UNDONE: "Consumption undone",
};

function fieldLabel(fieldName: string): string {
  return FIELD_LABELS[fieldName] ?? formatEnumLabel(fieldName);
}

function formatFieldValue(fieldName: string, value: string | null): string {
  if (value === null) {
    return "—";
  }
  if (fieldName === "status" || fieldName === "condition") {
    return formatEnumLabel(value);
  }
  if (fieldName === "purchase_date" || fieldName === "warranty_expiration") {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
  }
  return value;
}

function describeFieldChange(txn: InventoryTransaction): string {
  if (txn.field_name) {
    return `${fieldLabel(txn.field_name)}: ${formatFieldValue(txn.field_name, txn.old_value)} → ${formatFieldValue(txn.field_name, txn.new_value)}`;
  }
  return ACTION_SUMMARY[txn.transaction_type];
}

function formatQuantityDelta(delta: number | null): string {
  if (delta === null) {
    return "—";
  }
  return delta > 0 ? `+${delta}` : `${delta}`;
}

interface InventoryHistoryModalProps {
  item: InventoryItem;
  onClose: () => void;
}

export function InventoryHistoryModal({ item, onClose }: InventoryHistoryModalProps) {
  const [transactions, setTransactions] = useState<InventoryTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchInventoryItemTransactions(item.id, { limit: 500 })
      .then(setTransactions)
      .catch((err) => setError(getApiErrorMessage(err, "Could not load inventory history.")))
      .finally(() => setLoading(false));
  }, [item.id]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Modal title={`History — ${item.name}`} onClose={onClose} size="wide">
      {loading && <LoadingSpinner label="Loading history..." />}

      {!loading && error && (
        <div className={styles.errorWrap}>
          <ErrorMessage message={error} />
          <button type="button" className="btn btn-secondary btn-sm" onClick={load}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && transactions.length === 0 && (
        <EmptyState message="No inventory activity recorded yet." />
      )}

      {!loading && !error && transactions.length > 0 && (
        <div className={`tableShell ${styles.tableWrap}`}>
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>User</th>
                <th>Ticket</th>
                <th>Quantity Change</th>
                <th>Field Change</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn) => (
                <tr key={txn.id}>
                  <td className={styles.timestamp}>{new Date(txn.created_at).toLocaleString()}</td>
                  <td>
                    <InventoryTransactionTypeBadge transactionType={txn.transaction_type} />
                  </td>
                  <td>
                    {txn.performed_by.first_name} {txn.performed_by.last_name}
                  </td>
                  <td>
                    {txn.ticket ? (
                      <Link to={`/tickets/${txn.ticket.id}`} className={styles.ticketLink}>
                        {txn.ticket.ticket_number}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className={styles.numCell}>{formatQuantityDelta(txn.quantity_delta)}</td>
                  <td>{describeFieldChange(txn)}</td>
                  <td className={styles.notes}>{txn.notes ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}

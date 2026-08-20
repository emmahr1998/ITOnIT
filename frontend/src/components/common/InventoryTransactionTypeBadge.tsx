import type { InventoryTransactionType } from "../../types/inventoryTransaction";
import { formatEnumLabel } from "../../utils/formatEnumLabel";
// Reuses StatusBadge's own CSS module rather than duplicating the badge/
// color classes - same approach InventoryBadges.tsx already takes.
import styles from "./StatusBadge.module.css";

const TRANSACTION_TYPE_STYLE: Record<InventoryTransactionType, string> = {
  CREATED: styles.green,
  EDITED: styles.gray,
  STOCK_ADJUSTED: styles.blue,
  STATUS_CHANGED: styles.amber,
  HOLDER_CHANGED: styles.blue,
  LOCATION_CHANGED: styles.gray,
  RESERVED: styles.blue,
  RELEASED: styles.gray,
  CONSUMED: styles.amber,
  CONSUME_UNDONE: styles.gray,
};

export function InventoryTransactionTypeBadge({
  transactionType,
}: {
  transactionType: InventoryTransactionType;
}) {
  return (
    <span className={`${styles.badge} ${TRANSACTION_TYPE_STYLE[transactionType]}`}>
      {formatEnumLabel(transactionType)}
    </span>
  );
}

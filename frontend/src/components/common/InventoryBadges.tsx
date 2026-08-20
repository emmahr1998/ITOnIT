import type {
  InventoryCondition,
  InventoryStatus,
  InventoryTrackingType,
} from "../../types/inventoryItem";
import type { WarrantyState } from "../../utils/inventoryStatus";
import { formatEnumLabel } from "../../utils/formatEnumLabel";
// Reuses StatusBadge's own CSS module rather than duplicating the badge/
// color classes - same approach PriorityBadge already takes.
import styles from "./StatusBadge.module.css";

const STATUS_STYLE: Record<InventoryStatus, string> = {
  AVAILABLE: styles.green,
  RESERVED: styles.blue,
  IN_USE: styles.amber,
  IN_REPAIR: styles.red,
  RETIRED: styles.gray,
};

export function InventoryStatusBadge({ status }: { status: InventoryStatus }) {
  return (
    <span className={`${styles.badge} ${STATUS_STYLE[status]}`}>{formatEnumLabel(status)}</span>
  );
}

const TRACKING_TYPE_STYLE: Record<InventoryTrackingType, string> = {
  SERIALIZED: styles.blue,
  BULK: styles.gray,
};

export function TrackingTypeBadge({ trackingType }: { trackingType: InventoryTrackingType }) {
  return (
    <span className={`${styles.badge} ${TRACKING_TYPE_STYLE[trackingType]}`}>
      {formatEnumLabel(trackingType)}
    </span>
  );
}

const CONDITION_STYLE: Record<InventoryCondition, string> = {
  NEW: styles.blue,
  GOOD: styles.green,
  FAIR: styles.amber,
  DAMAGED: styles.red,
  BROKEN: styles.red,
};

export function ConditionBadge({ condition }: { condition: InventoryCondition | null }) {
  if (!condition) {
    return <span>—</span>;
  }
  return (
    <span className={`${styles.badge} ${CONDITION_STYLE[condition]}`}>
      {formatEnumLabel(condition)}
    </span>
  );
}

export function LowStockBadge() {
  return <span className={`${styles.badge} ${styles.amber}`}>Low Stock</span>;
}

export function WarrantyBadge({ state }: { state: WarrantyState }) {
  if (!state) {
    return null;
  }
  return (
    <span className={`${styles.badge} ${state === "expired" ? styles.red : styles.amber}`}>
      {state === "expired" ? "Warranty Expired" : "Warranty Expiring"}
    </span>
  );
}

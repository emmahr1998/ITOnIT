import { useEffect, useState } from "react";
import { Modal } from "../common/Modal";
import { ErrorMessage } from "../common/ErrorMessage";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { EmptyState } from "../common/EmptyState";
import { fetchInventoryItems } from "../../api/inventoryItems";
import { reserveTicketInventory } from "../../api/ticketInventory";
import { getApiErrorMessage } from "../../api/client";
import type { InventoryItem } from "../../types/inventoryItem";
import type { TicketInventoryUsage } from "../../types/ticketInventory";
import styles from "./TicketInventoryReserveModal.module.css";

const SEARCH_DEBOUNCE_MS = 300;

interface TicketInventoryReserveModalProps {
  ticketId: number;
  onClose: () => void;
  onReserved: (usage: TicketInventoryUsage) => void;
}

export function TicketInventoryReserveModal({
  ticketId,
  onClose,
  onReserved,
}: TicketInventoryReserveModalProps) {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selected, setSelected] = useState<InventoryItem | null>(null);
  const [quantity, setQuantity] = useState("1");
  const [reserving, setReserving] = useState(false);
  const [reserveError, setReserveError] = useState<string | null>(null);

  useEffect(() => {
    const timeout = setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    // Only AVAILABLE items are reservable at all; category-active is
    // filtered client-side since the list endpoint has no such param -
    // both are defense-in-depth on top of the same checks the backend
    // still enforces on the actual reserve request.
    fetchInventoryItems({ search: search || undefined, status: "AVAILABLE", limit: 20 })
      .then((items) => !cancelled && setResults(items.filter((i) => i.inventory_category.is_active)))
      .catch((err) => !cancelled && setLoadError(getApiErrorMessage(err, "Could not search inventory.")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [search]);

  const isBulk = selected?.tracking_type === "BULK";
  const maxQuantity = selected ? selected.stock_quantity - selected.reserved_quantity : 1;

  function selectItem(item: InventoryItem) {
    setSelected(item);
    setQuantity("1");
    setReserveError(null);
  }

  async function handleReserve() {
    if (!selected) {
      return;
    }
    setReserving(true);
    setReserveError(null);
    try {
      const usage = await reserveTicketInventory(ticketId, {
        inventory_item_id: selected.id,
        quantity: isBulk ? Number(quantity) : 1,
      });
      onReserved(usage);
    } catch (err) {
      setReserveError(getApiErrorMessage(err, "Could not reserve this item."));
    } finally {
      setReserving(false);
    }
  }

  return (
    <Modal title="Reserve Inventory Item" onClose={onClose}>
      <div className={styles.body}>
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search by asset tag, name, manufacturer, model, category..."
          className="input"
          autoFocus
        />

        {loading && <LoadingSpinner label="Searching..." />}
        {loadError && <ErrorMessage message={loadError} />}

        {!loading && !loadError && (
          <ul className={styles.results}>
            {results.length === 0 ? (
              <EmptyState message="No available inventory matches your search." />
            ) : (
              results.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={
                      selected?.id === item.id ? styles.resultButtonActive : styles.resultButton
                    }
                    onClick={() => selectItem(item)}
                  >
                    <span className={styles.resultName}>{item.name}</span>
                    <span className={styles.resultMeta}>
                      {item.asset_tag ? `${item.asset_tag} · ` : ""}
                      {item.inventory_category.name} ·{" "}
                      {item.tracking_type === "SERIALIZED"
                        ? "Serialized"
                        : `Bulk (${item.stock_quantity - item.reserved_quantity} available)`}
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>
        )}

        {selected && isBulk && (
          <label className="field">
            <span className="fieldLabel">Quantity</span>
            <input
              type="number"
              min={1}
              max={maxQuantity}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="input"
            />
          </label>
        )}

        {reserveError && <ErrorMessage message={reserveError} />}

        <div className={styles.actions}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={
              !selected ||
              reserving ||
              (isBulk && (Number(quantity) < 1 || Number(quantity) > maxQuantity))
            }
            onClick={handleReserve}
          >
            {reserving ? "Reserving..." : "Reserve"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

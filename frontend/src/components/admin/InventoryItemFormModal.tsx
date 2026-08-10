import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "../common/Modal";
import { ErrorMessage } from "../common/ErrorMessage";
import { createInventoryItem, updateInventoryItem } from "../../api/inventoryItems";
import { fetchUsers } from "../../api/users";
import { getApiErrorMessage } from "../../api/client";
import {
  BULK_STATUSES,
  INVENTORY_CONDITIONS,
  SERIALIZED_STATUSES,
  type InventoryCondition,
  type InventoryItem,
  type InventoryItemCreate,
  type InventoryStatus,
  type InventoryTrackingType,
} from "../../types/inventoryItem";
import type { InventoryCategory } from "../../types/inventoryCategory";
import type { Location } from "../../types/location";
import type { AdminUser } from "../../types/user";
import styles from "./InventoryItemFormModal.module.css";

interface InventoryItemFormModalProps {
  mode: "create" | "edit";
  item?: InventoryItem;
  categories: InventoryCategory[];
  locations: Location[];
  onClose: () => void;
  onSaved: (item: InventoryItem) => void;
}

function toNullable(value: string): string | null {
  return value.trim() === "" ? null : value.trim();
}

/** Converts an ISO datetime/date string to the yyyy-mm-dd an <input type="date"> needs. */
function toDateInputValue(value: string | null): string {
  return value ? value.slice(0, 10) : "";
}

export function InventoryItemFormModal({
  mode,
  item,
  categories,
  locations,
  onClose,
  onSaved,
}: InventoryItemFormModalProps) {
  const [trackingType, setTrackingType] = useState<InventoryTrackingType>(
    item?.tracking_type ?? "SERIALIZED",
  );
  const [categoryId, setCategoryId] = useState(item?.inventory_category.id.toString() ?? "");
  const [name, setName] = useState(item?.name ?? "");
  const [status, setStatus] = useState<InventoryStatus>(item?.status ?? "AVAILABLE");
  const [condition, setCondition] = useState<InventoryCondition | "">(item?.condition ?? "");
  const [assetTag, setAssetTag] = useState(item?.asset_tag ?? "");
  const [manufacturer, setManufacturer] = useState(item?.manufacturer ?? "");
  const [model, setModel] = useState(item?.model ?? "");
  const [serialNumber, setSerialNumber] = useState(item?.serial_number ?? "");
  const [stockQuantity, setStockQuantity] = useState(
    item?.tracking_type === "BULK" ? String(item.stock_quantity) : "",
  );
  const [minimumStock, setMinimumStock] = useState(item?.minimum_stock?.toString() ?? "");
  const [locationId, setLocationId] = useState(item?.current_location?.id.toString() ?? "");
  const [holderUserId, setHolderUserId] = useState(item?.current_holder?.id.toString() ?? "");
  const [purchaseDate, setPurchaseDate] = useState(toDateInputValue(item?.purchase_date ?? null));
  const [warrantyExpiration, setWarrantyExpiration] = useState(
    toDateInputValue(item?.warranty_expiration ?? null),
  );
  const [supplier, setSupplier] = useState(item?.supplier ?? "");
  const [purchaseCost, setPurchaseCost] = useState(item?.purchase_cost ?? "");
  const [invoiceNumber, setInvoiceNumber] = useState(item?.invoice_number ?? "");
  const [notes, setNotes] = useState(item?.notes ?? "");

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSerialized = trackingType === "SERIALIZED";
  const statusOptions = isSerialized ? SERIALIZED_STATUSES : BULK_STATUSES;

  // The holder select is Company-Administrator-only territory (this modal
  // never renders for Technician), so fetching the full user list here -
  // rather than deriving it from loaded inventory items, as the page's
  // holder *filter* does - is safe and gives every company user as a
  // candidate, not just ones already holding something.
  useEffect(() => {
    fetchUsers({ limit: 500 })
      .then(setUsers)
      .catch(() => {
        // The holder dropdown is a convenience; saving without a holder still works.
      });
  }, []);

  // Switching tracking type clears fields that don't apply to the new type,
  // so a stray value from before the switch can never be silently submitted.
  function handleTrackingTypeChange(next: InventoryTrackingType) {
    setTrackingType(next);
    if (next === "BULK") {
      setAssetTag("");
      setCondition("");
      setHolderUserId("");
      if (!BULK_STATUSES.includes(status)) {
        setStatus("AVAILABLE");
      }
    } else {
      setStockQuantity("");
      setMinimumStock("");
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const shared = {
      inventory_category_id: Number(categoryId),
      name: name.trim(),
      status,
      manufacturer: toNullable(manufacturer),
      model: toNullable(model),
      serial_number: toNullable(serialNumber),
      current_location_id: locationId ? Number(locationId) : null,
      purchase_date: toNullable(purchaseDate),
      warranty_expiration: toNullable(warrantyExpiration),
      supplier: toNullable(supplier),
      purchase_cost: toNullable(purchaseCost),
      invoice_number: toNullable(invoiceNumber),
      notes: toNullable(notes),
      condition: isSerialized ? toNullable(condition) as InventoryCondition | null : null,
      asset_tag: isSerialized ? toNullable(assetTag) : null,
      current_holder_user_id: isSerialized && holderUserId ? Number(holderUserId) : null,
      minimum_stock: isSerialized ? null : minimumStock === "" ? null : Number(minimumStock),
    };

    try {
      if (mode === "create") {
        const payload: InventoryItemCreate = {
          ...shared,
          tracking_type: trackingType,
          stock_quantity: isSerialized ? undefined : Number(stockQuantity),
        };
        const created = await createInventoryItem(payload);
        onSaved(created);
      } else if (item) {
        const updated = await updateInventoryItem(item.id, {
          ...shared,
          stock_quantity: isSerialized ? undefined : Number(stockQuantity),
        });
        onSaved(updated);
      }
    } catch (err) {
      setError(getApiErrorMessage(err, `Could not ${mode === "create" ? "create" : "save"} this item.`));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={mode === "create" ? "Add Inventory Item" : `Edit ${item?.name ?? "Item"}`}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className={styles.form}>
        {mode === "create" && (
          <div className={styles.trackingToggle} role="radiogroup" aria-label="Tracking type">
            <button
              type="button"
              className={isSerialized ? styles.trackingButtonActive : styles.trackingButton}
              onClick={() => handleTrackingTypeChange("SERIALIZED")}
              aria-pressed={isSerialized}
            >
              Serialized Asset
              <span className={styles.trackingButtonHint}>One physical unit - a laptop, a monitor</span>
            </button>
            <button
              type="button"
              className={!isSerialized ? styles.trackingButtonActive : styles.trackingButton}
              onClick={() => handleTrackingTypeChange("BULK")}
              aria-pressed={!isSerialized}
            >
              Bulk Stock
              <span className={styles.trackingButtonHint}>A quantity of interchangeable stock - cables, mice</span>
            </button>
          </div>
        )}
        {mode === "edit" && (
          <p className={styles.trackingLocked}>
            Tracking type: <strong>{isSerialized ? "Serialized Asset" : "Bulk Stock"}</strong>{" "}
            (cannot be changed after creation)
          </p>
        )}

        <div className={styles.row}>
          <label className="field">
            <span className="fieldLabel">
              Name<span className="requiredMark">*</span>
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="input"
              autoFocus
            />
          </label>
          <label className="field">
            <span className="fieldLabel">
              Category<span className="requiredMark">*</span>
            </span>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              required
              className="select"
            >
              <option value="" disabled>
                Select a category
              </option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className={styles.row}>
          {isSerialized ? (
            <label className="field">
              <span className="fieldLabel">
                Asset Tag<span className="requiredMark">*</span>
              </span>
              <input
                type="text"
                value={assetTag}
                onChange={(e) => setAssetTag(e.target.value)}
                required
                className="input"
                placeholder="e.g. LAP-0001"
              />
            </label>
          ) : (
            <label className="field">
              <span className="fieldLabel">
                Stock Quantity<span className="requiredMark">*</span>
              </span>
              <input
                type="number"
                min={0}
                value={stockQuantity}
                onChange={(e) => setStockQuantity(e.target.value)}
                required
                className="input"
              />
            </label>
          )}

          <label className="field">
            <span className="fieldLabel">Status</span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as InventoryStatus)}
              className="select"
            >
              {statusOptions.map((s) => (
                <option key={s} value={s}>
                  {s.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </div>

        {isSerialized ? (
          <div className={styles.row}>
            <label className="field">
              <span className="fieldLabel">Stock Quantity</span>
              <input type="number" value="1" disabled className="input" />
            </label>
            <label className="field">
              <span className="fieldLabel">Condition</span>
              <select
                value={condition}
                onChange={(e) => setCondition(e.target.value as InventoryCondition | "")}
                className="select"
              >
                <option value="">Not set</option>
                {INVENTORY_CONDITIONS.map((c) => (
                  <option key={c} value={c}>
                    {c[0] + c.slice(1).toLowerCase()}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : (
          <div className={styles.row}>
            <label className="field">
              <span className="fieldLabel">Minimum Stock</span>
              <input
                type="number"
                min={0}
                value={minimumStock}
                onChange={(e) => setMinimumStock(e.target.value)}
                className="input"
                placeholder="Low-stock threshold"
              />
            </label>
            <div />
          </div>
        )}

        <div className={styles.row}>
          <label className="field">
            <span className="fieldLabel">Manufacturer</span>
            <input
              type="text"
              value={manufacturer}
              onChange={(e) => setManufacturer(e.target.value)}
              className="input"
            />
          </label>
          <label className="field">
            <span className="fieldLabel">Model</span>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="input"
            />
          </label>
        </div>

        <div className={styles.row}>
          <label className="field">
            <span className="fieldLabel">Serial Number</span>
            <input
              type="text"
              value={serialNumber}
              onChange={(e) => setSerialNumber(e.target.value)}
              className="input"
            />
          </label>
          <label className="field">
            <span className="fieldLabel">Location</span>
            <select
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              className="select"
            >
              <option value="">No location</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.title}
                </option>
              ))}
            </select>
          </label>
        </div>

        {isSerialized && (
          <div className={styles.row}>
            <label className="field">
              <span className="fieldLabel">Current Holder</span>
              <select
                value={holderUserId}
                onChange={(e) => setHolderUserId(e.target.value)}
                className="select"
              >
                <option value="">Unassigned</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.first_name} {u.last_name}
                  </option>
                ))}
              </select>
            </label>
            <div />
          </div>
        )}

        <div className={styles.row}>
          <label className="field">
            <span className="fieldLabel">Purchase Date</span>
            <input
              type="date"
              value={purchaseDate}
              onChange={(e) => setPurchaseDate(e.target.value)}
              className="input"
            />
          </label>
          <label className="field">
            <span className="fieldLabel">Warranty Expiration</span>
            <input
              type="date"
              value={warrantyExpiration}
              onChange={(e) => setWarrantyExpiration(e.target.value)}
              className="input"
            />
          </label>
        </div>

        <div className={styles.row}>
          <label className="field">
            <span className="fieldLabel">Supplier</span>
            <input
              type="text"
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              className="input"
            />
          </label>
          <label className="field">
            <span className="fieldLabel">Purchase Cost</span>
            <input
              type="number"
              min={0}
              step="0.01"
              value={purchaseCost}
              onChange={(e) => setPurchaseCost(e.target.value)}
              className="input"
            />
          </label>
        </div>

        <label className="field">
          <span className="fieldLabel">Invoice Number</span>
          <input
            type="text"
            value={invoiceNumber}
            onChange={(e) => setInvoiceNumber(e.target.value)}
            className="input"
          />
        </label>

        <label className="field">
          <span className="fieldLabel">Notes</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="textarea"
            rows={3}
          />
        </label>

        {error && <ErrorMessage message={error} />}

        <div className={styles.actions}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving || !categoryId}>
            {saving ? "Saving..." : mode === "create" ? "Add Item" : "Save Changes"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

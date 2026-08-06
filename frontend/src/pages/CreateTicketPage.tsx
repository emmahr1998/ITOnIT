import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { PlusCircle } from "lucide-react";
import { fetchCategories } from "../api/categories";
import { fetchPriorities } from "../api/priorities";
import { fetchLocations } from "../api/locations";
import { createTicket } from "../api/tickets";
import { getApiErrorMessage } from "../api/client";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import type { Category } from "../types/category";
import type { Priority } from "../types/priority";
import type { Location } from "../types/location";
import styles from "./CreateTicketPage.module.css";

export function CreateTicketPage() {
  const navigate = useNavigate();

  const [categories, setCategories] = useState<Category[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [priorityId, setPriorityId] = useState("");
  const [locationId, setLocationId] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchCategories(), fetchPriorities(), fetchLocations()])
      .then(([categoryList, priorityList, locationList]) => {
        setCategories(categoryList);
        setPriorities(priorityList);
        setLocations(locationList.filter((location) => location.is_active));
      })
      .catch((err) => setOptionsError(getApiErrorMessage(err, "Could not load form options.")))
      .finally(() => setLoadingOptions(false));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!categoryId || !priorityId) {
      setSubmitError("Please choose a category and priority.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      const ticket = await createTicket({
        title,
        description,
        category_id: Number(categoryId),
        priority_id: Number(priorityId),
        location_id: locationId ? Number(locationId) : null,
      });
      navigate(`/tickets/${ticket.id}`);
    } catch (err) {
      setSubmitError(getApiErrorMessage(err, "Could not create the ticket."));
    } finally {
      setSubmitting(false);
    }
  }

  if (loadingOptions) {
    return <LoadingSpinner label="Loading form..." />;
  }

  return (
    <div className={styles.page}>
      <div>
        <h1 className={styles.heading}>Create Ticket</h1>
        <p className={styles.subheading}>
          Describe the issue and we'll route it to the right team.
        </p>
      </div>

      {optionsError && <ErrorMessage message={optionsError} />}

      <form onSubmit={handleSubmit} className={styles.form}>
        <label className="field">
          <span className="fieldLabel">
            Title<span className="requiredMark">*</span>
          </span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={200}
            placeholder="e.g. Laptop won't turn on"
            className="input"
          />
        </label>

        <label className="field">
          <span className="fieldLabel">
            Description<span className="requiredMark">*</span>
          </span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            rows={5}
            placeholder="Include any steps you've already tried."
            className="textarea"
          />
        </label>

        <div className={styles.row}>
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
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="fieldLabel">
              Priority<span className="requiredMark">*</span>
            </span>
            <select
              value={priorityId}
              onChange={(e) => setPriorityId(e.target.value)}
              required
              className="select"
            >
              <option value="" disabled>
                Select a priority
              </option>
              {priorities.map((priority) => (
                <option key={priority.id} value={priority.id}>
                  {priority.title}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="field">
          <span className="fieldLabel">Location</span>
          <select
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            className="select"
          >
            <option value="">No location</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.title}
              </option>
            ))}
          </select>
        </label>

        {submitError && <ErrorMessage message={submitError} />}

        <div className={styles.actions}>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            <PlusCircle size={16} /> {submitting ? "Creating..." : "Create Ticket"}
          </button>
        </div>
      </form>
    </div>
  );
}

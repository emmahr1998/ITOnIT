import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Download, Paperclip, Upload } from "lucide-react";
import { downloadAttachment, fetchAttachments, uploadAttachment } from "../../api/attachments";
import { getApiErrorMessage } from "../../api/client";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { ErrorMessage } from "../common/ErrorMessage";
import { EmptyState } from "../common/EmptyState";
import type { Attachment } from "../../types/attachment";
import styles from "./AttachmentSection.module.css";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AttachmentSection({ ticketId }: { ticketId: number }) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAttachments(ticketId)
      .then((data) => !cancelled && setAttachments(data))
      .catch(
        (err) => !cancelled && setError(getApiErrorMessage(err, "Could not load attachments.")),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  async function handleFileSelected(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) {
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const attachment = await uploadAttachment(ticketId, file);
      setAttachments((prev) => [...prev, attachment]);
    } catch (err) {
      setUploadError(getApiErrorMessage(err, "Could not upload the file."));
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleDownload(attachment: Attachment) {
    try {
      await downloadAttachment(ticketId, attachment.id, attachment.original_filename);
    } catch (err) {
      setUploadError(getApiErrorMessage(err, "Could not download the file."));
    }
  }

  return (
    <section className="sectionCard">
      <h2 className="sectionHeading">
        <Paperclip size={18} strokeWidth={2} /> Attachments
        {attachments.length > 0 && <span className={styles.count}>{attachments.length}</span>}
      </h2>

      {loading && <LoadingSpinner label="Loading attachments..." />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && (
        <>
          {attachments.length === 0 ? (
            <EmptyState message="No files attached yet." />
          ) : (
            <ul className={styles.list}>
              {attachments.map((attachment) => (
                <li key={attachment.id} className={styles.item}>
                  <div className={styles.itemInfo}>
                    <Paperclip size={16} className={styles.itemIcon} aria-hidden="true" />
                    <div>
                      <p className={styles.filename}>{attachment.original_filename}</p>
                      <p className={styles.meta}>
                        {formatSize(attachment.file_size)} &middot; uploaded by{" "}
                        {attachment.uploaded_by.first_name} {attachment.uploaded_by.last_name}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleDownload(attachment)}
                  >
                    <Download size={14} /> Download
                  </button>
                </li>
              ))}
            </ul>
          )}

          {uploadError && <ErrorMessage message={uploadError} />}

          <div className={styles.uploadRow}>
            <label className={styles.uploadButton}>
              <Upload size={14} />
              {uploading ? "Uploading..." : "Upload File"}
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileSelected}
                disabled={uploading}
                className={styles.hiddenFileInput}
              />
            </label>
          </div>
        </>
      )}
    </section>
  );
}

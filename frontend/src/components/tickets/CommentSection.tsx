import { useEffect, useState, type FormEvent } from "react";
import { MessageSquare, Send } from "lucide-react";
import { addComment, fetchComments } from "../../api/comments";
import { getApiErrorMessage } from "../../api/client";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { ErrorMessage } from "../common/ErrorMessage";
import { EmptyState } from "../common/EmptyState";
import type { Comment } from "../../types/comment";
import styles from "./CommentSection.module.css";

function initials(firstName: string, lastName: string): string {
  return `${firstName[0] ?? ""}${lastName[0] ?? ""}`.toUpperCase();
}

export function CommentSection({ ticketId }: { ticketId: number }) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchComments(ticketId)
      .then((data) => !cancelled && setComments(data))
      .catch((err) => !cancelled && setError(getApiErrorMessage(err, "Could not load comments.")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const comment = await addComment(ticketId, content.trim());
      setComments((prev) => [...prev, comment]);
      setContent("");
    } catch (err) {
      setSubmitError(getApiErrorMessage(err, "Could not post your comment."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="sectionCard">
      <h2 className="sectionHeading">
        <MessageSquare size={18} strokeWidth={2} /> Comments
        {comments.length > 0 && <span className={styles.count}>{comments.length}</span>}
      </h2>

      {loading && <LoadingSpinner label="Loading comments..." />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && (
        <>
          {comments.length === 0 ? (
            <EmptyState message="No comments yet. Be the first to add one." />
          ) : (
            <ul className={styles.list}>
              {comments.map((comment) => (
                <li key={comment.id} className={styles.comment}>
                  <span className={styles.avatar} aria-hidden="true">
                    {initials(comment.author.first_name, comment.author.last_name)}
                  </span>
                  <div className={styles.commentBody}>
                    <div className={styles.commentHeader}>
                      <span className={styles.author}>
                        {comment.author.first_name} {comment.author.last_name}
                      </span>
                      <span className={styles.timestamp}>
                        {new Date(comment.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className={styles.content}>{comment.content}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={handleSubmit} className={styles.form}>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Add a comment..."
              className="textarea"
              rows={3}
              disabled={submitting}
            />
            {submitError && <ErrorMessage message={submitError} />}
            <div className={styles.formActions}>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                <Send size={14} /> {submitting ? "Posting..." : "Post Comment"}
              </button>
            </div>
          </form>
        </>
      )}
    </section>
  );
}

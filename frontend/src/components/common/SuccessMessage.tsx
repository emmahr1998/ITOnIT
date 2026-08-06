import { useEffect } from "react";
import { CheckCircle2 } from "lucide-react";
import styles from "./SuccessMessage.module.css";

interface SuccessMessageProps {
  message: string;
  onDismiss?: () => void;
  /** How long before it auto-dismisses, in ms. Set to 0 to keep it visible. */
  duration?: number;
}

/** A small, transient inline confirmation - not a persistent notification system. */
export function SuccessMessage({ message, onDismiss, duration = 2500 }: SuccessMessageProps) {
  useEffect(() => {
    if (!onDismiss || duration <= 0) {
      return;
    }
    const timeout = setTimeout(onDismiss, duration);
    return () => clearTimeout(timeout);
  }, [onDismiss, duration]);

  return (
    <p className={styles.message} role="status">
      <CheckCircle2 size={16} strokeWidth={2} />
      {message}
    </p>
  );
}

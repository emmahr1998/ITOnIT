import { AlertCircle } from "lucide-react";
import styles from "./ErrorMessage.module.css";

interface ErrorMessageProps {
  message: string;
}

export function ErrorMessage({ message }: ErrorMessageProps) {
  return (
    <p className={styles.message} role="alert">
      <AlertCircle size={16} strokeWidth={2} className={styles.icon} />
      {message}
    </p>
  );
}

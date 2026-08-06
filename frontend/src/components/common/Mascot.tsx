import logo from "../../assets/logo-512.png";
import styles from "./Mascot.module.css";

interface MascotProps {
  size?: number;
  className?: string;
  rounded?: boolean;
}

/** The ITOnIT running-mascot brand mark - reused across login, sidebar, loading, and empty states. */
export function Mascot({ size = 48, className, rounded = true }: MascotProps) {
  return (
    <img
      src={logo}
      alt="ITOnIT mascot"
      width={size}
      height={size}
      className={[styles.mascot, rounded ? styles.rounded : "", className].filter(Boolean).join(" ")}
    />
  );
}

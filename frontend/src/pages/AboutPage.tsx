import { useEffect, useState } from "react";
import { Mascot } from "../components/common/Mascot";
import { fetchHealth } from "../api/health";
import styles from "./AboutPage.module.css";

export function AboutPage() {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((health) => setVersion(health.version))
      .catch(() => {
        // Version display is a nice-to-have; the page still works without it.
      });
  }, []);

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <Mascot size={96} />
        <h1 className={styles.title}>ITOnIT</h1>
        <p className={styles.tagline}>Fast, modern IT support for your organization.</p>
        <p className={styles.body}>
          ITOnIT is a company-managed IT help desk: employees submit and track support tickets,
          technicians resolve them, and managers and administrators keep the whole operation
          running - departments, categories, priorities, locations, and user accounts all in one
          place.
        </p>
        <dl className={styles.meta}>
          <div>
            <dt>Version</dt>
            <dd>{version ?? "—"}</dd>
          </div>
          <div>
            <dt>Built with</dt>
            <dd>React, TypeScript, FastAPI</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

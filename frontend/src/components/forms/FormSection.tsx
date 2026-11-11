import { useId, type ReactNode } from "react";
import styles from "./form-section.module.css";

export function FormSection({ title, description, children }: {
  title: string; description?: string; children: ReactNode;
}) {
  const descriptionId = useId();
  return <fieldset className={styles.section} aria-describedby={description ? descriptionId : undefined}>
    <legend className={styles.legend}>{title}</legend>
    {description && <p id={descriptionId} className={styles.description}>{description}</p>}
    <div className={styles.grid}>{children}</div>
  </fieldset>;
}

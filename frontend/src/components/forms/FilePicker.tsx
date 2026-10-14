"use client";
/**
 * Choosing a file to upload, the same on every screen (PROJECT-FILES-003): what is accepted and up to what size (from
 * the one server policy), the chosen file's name and size, and why it is refused before anything is sent.
 * The server checks it again and makes images small; a refused file never reaches `onFile`.
 */
import { useRef, useState, type CSSProperties } from "react";
import { useTranslations } from "next-intl";

import { acceptOf, fileProblem, formatBytes, limitGroups, useFilePolicy, type FileProblem, type KindPolicy, type UploadKind } from "@/lib/files";

/** "PNG, JPEG, WebP up to 5 MB · PDF up to 2 MB", in the screen's language. */
export function FileLimits({ kind, className, style }: { kind: UploadKind; className?: string; style?: CSSProperties }) {
  const t = useTranslations("common.files");
  const policy = useFilePolicy(kind);
  if (!policy) return null;
  const size = (bytes: number) => formatBytes(bytes, (key) => t(`units.${key}`));
  return <span className={className} style={style}>
    {limitGroups(policy).map(([types, limit]) => t("upTo", { types, size: size(limit) })).join(" · ")}
    {kind === "logo" ? ` · ${t("logoStoredSmall")}` : ` · ${t("imagesStoredSmall")}`}
  </span>;
}

/** The message for a refused file, in the screen's language. */
export function useFileProblemText() {
  const t = useTranslations("common.files");
  return (problem: FileProblem, policy: KindPolicy | null) => {
    if (problem.code === "TOO_LARGE") return t("tooLarge", { size: formatBytes(problem.limit, (key) => t(`units.${key}`)) });
    if (problem.code === "EMPTY") return t("empty");
    return t("unsupported", { types: policy ? limitGroups(policy).map(([types]) => types).join(", ") : "" });
  };
}

export function FilePicker({ kind, label, busy, busyLabel, disabled, onFile, onError, className, hintClassName, showLimits = true }: {
  kind: UploadKind; label: string; busy?: boolean; busyLabel?: string; disabled?: boolean;
  onFile: (file: File) => void | Promise<void>; onError?: (message: string) => void;
  className?: string; hintClassName?: string; showLimits?: boolean;
}) {
  const policy = useFilePolicy(kind);
  const problemText = useFileProblemText();
  const t = useTranslations("common.files");
  const picker = useRef<HTMLInputElement>(null);
  const [chosen, setChosen] = useState<File | null>(null);
  const [error, setError] = useState("");
  function choose(file: File | undefined) {
    if (picker.current) picker.current.value = "";
    if (!file) return;
    const problem = fileProblem(file, policy);
    if (problem) {
      const message = problemText(problem, policy);
      setError(message);
      setChosen(null);
      onError?.(message);
      return;
    }
    setError("");
    setChosen(file);
    void onFile(file);
  }
  return <span style={{ display: "inline-flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
    <input ref={picker} type="file" hidden accept={acceptOf(policy, kind)} aria-label={label} disabled={disabled || busy}
      onChange={(e) => choose(e.target.files?.[0])} />
    <button type="button" className={className} disabled={disabled || busy} onClick={() => picker.current?.click()}>{busy && busyLabel ? busyLabel : label}</button>
    {showLimits && <FileLimits kind={kind} className={hintClassName} />}
    {chosen && busy && <span className={hintClassName}>{chosen.name} · {formatBytes(chosen.size, (key) => t(`units.${key}`))}</span>}
    {error && !onError && <span role="alert" style={{ color: "var(--danger)" }}>{error}</span>}
  </span>;
}

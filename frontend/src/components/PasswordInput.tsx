"use client";

import type { CSSProperties, InputHTMLAttributes } from "react";
import { useState } from "react";
import { useTranslations } from "next-intl";

type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  inputStyle?: CSSProperties;
};

const styles: Record<string, CSSProperties> = {
  wrapper: {
    position: "relative",
  },
  toggleButton: {
    position: "absolute",
    insetInlineEnd: "8px",
    top: "50%",
    transform: "translateY(-50%)",
    background: "none",
    border: "none",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    padding: "4px",
    color: "#7b8794",
  },
};

const iconBase = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

function IconEye() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" {...iconBase}>
      <path d="M2 12s3.8-7 10-7 10 7 10 7-3.8 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconEyeOff() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" {...iconBase}>
      <path d="M3 3l18 18" />
      <path d="M10.6 5.2c.45-.08.92-.12 1.4-.12 6.2 0 10 7 10 7a17 17 0 0 1-3.6 4.5M6.6 6.6A17 17 0 0 0 2 12s3.8 7 10 7c1.5 0 2.85-.3 4-.8" />
      <path d="M9.5 9.7a3 3 0 0 0 4.2 4.2" />
    </svg>
  );
}

export function PasswordInput({ style, inputStyle, ...props }: PasswordInputProps) {
  const t = useTranslations("common");
  const [visible, setVisible] = useState(false);

  return (
    <div style={{ ...styles.wrapper, ...style }}>
      <input
        {...props}
        type={visible ? "text" : "password"}
        style={{ ...inputStyle, paddingInlineEnd: "38px", boxSizing: "border-box", width: "100%" }}
      />
      <button
        type="button"
        style={styles.toggleButton}
        onClick={() => setVisible((current) => !current)}
        aria-label={visible ? t("passwordToggle.hide") : t("passwordToggle.show")}
        tabIndex={-1}
      >
        {visible ? <IconEyeOff /> : <IconEye />}
      </button>
    </div>
  );
}

"use client";
/**
 * A finished action's message (PROJECT-UX-NOTIFY): shown as the standard notification at the top of the screen, and
 * the screen moves on at once (onOk), instead of a window the user had to close. Kept under its old name so every
 * screen that used it gets the same behaviour.
 */
import { useEffect, useRef } from "react";

import { pushNote } from "@/components/notify/Notifications";

type SuccessModalProps = {
  message: string;
  onOk: () => void;
  okLabel?: string;
};

export function SuccessModal({ message, onOk }: SuccessModalProps) {
  const shown = useRef(false);
  useEffect(() => {
    if (shown.current) return;  // once, even under React's double effects in development
    shown.current = true;
    pushNote("success", message);
    onOk();
  }, [message, onOk]);
  return null;
}

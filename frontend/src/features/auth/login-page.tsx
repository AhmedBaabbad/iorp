"use client";

import { useRouter } from "next/navigation";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api-client";
import { sharedStyles } from "@/styles/shared-styles";
import { useAuth } from "./auth-context";

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    background: "#f6f7f9",
    color: "#1f2933",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding: "24px",
  },
  panel: {
    width: "100%",
    maxWidth: "420px",
    background: "#ffffff",
    border: "1px solid #d9dee7",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.08)",
    padding: "32px",
  },
  header: {
    marginBottom: "28px",
  },
  eyebrow: {
    margin: "0 0 8px",
    color: "#52606d",
    fontSize: "14px",
    fontWeight: 600,
  },
  title: {
    margin: 0,
    fontSize: "28px",
    lineHeight: 1.2,
  },
  form: {
    display: "grid",
    gap: "18px",
  },
};

export function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading } = useAuth();
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/customers");
    }
  }, [isAuthenticated, isLoading, router]);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login({ email, password });
      router.replace("/customers");
    } catch (caughtError) {
      const message =
        caughtError instanceof ApiClientError && caughtError.status === 401
          ? "Invalid email or password."
          : "Unable to sign in. Please try again.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main style={styles.page}>
      <section style={styles.panel} aria-labelledby="login-title">
        <div style={styles.header}>
          <p style={styles.eyebrow}>IORP v0.1</p>
          <h1 id="login-title" style={styles.title}>
            Sign in
          </h1>
        </div>

        <form style={styles.form} onSubmit={handleSubmit}>
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>Email</span>
            <input
              style={sharedStyles.input}
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>Password</span>
            <input
              style={sharedStyles.input}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <button
            style={{ ...sharedStyles.button, width: "100%" }}
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

export type StepAction = { method: string; path: string; body?: unknown; token?: string | null };
export type Pending = { action: StepAction; resolve: (token: string) => void; reject: (error: Error) => void };
export function requestStepUp(action: StepAction): Promise<string> {
  return new Promise((resolve, reject) => {
    window.dispatchEvent(new CustomEvent<Pending>("iorp-platform-step-up", { detail: { action, resolve, reject } }));
  });
}

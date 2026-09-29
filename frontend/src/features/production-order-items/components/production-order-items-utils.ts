export function isReadOnlyStatus(status: string) {
  // Mirrors the backend: finished orders (completed, closed, cancelled) accept no item changes.
  return status === "cancelled" || status === "completed" || status === "closed";
}

export function formatStatus(status: string) {
  return status.replace("_", " ");
}

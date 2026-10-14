import { MySessionsPage } from "@/features/auth/my-sessions-page";

/** Every signed-in user's own sessions: no permission needed (SEC-001). */
export default function Page() {
  return <MySessionsPage />;
}

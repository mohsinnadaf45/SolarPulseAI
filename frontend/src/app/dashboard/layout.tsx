// Server Component — can import CSS safely with Turbopack
import "./dashboard.css";
import { DashboardShell } from "./DashboardShell";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell>{children}</DashboardShell>;
}

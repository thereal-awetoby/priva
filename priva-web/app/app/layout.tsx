import "./app.css";
import type { ReactNode } from "react";
import AuthGuard from "@/components/app/AuthGuard";

export default function AppLayout({ children }: { children: ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
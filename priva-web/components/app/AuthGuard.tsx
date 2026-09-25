"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let mounted = true;
    let supabase;

    try {
      supabase = createClient();
    } catch (error) {
      console.error(error);
      setChecking(false);
      return;
    }

    supabase.auth.getSession().then(({ data: { session } }: { data: { session: Session | null } }) => {
      if (!session) {
        window.location.replace("/?auth=login");
        return;
      }
      if (mounted) setChecking(false);
    });

    const { data } = supabase.auth.onAuthStateChange((_event: AuthChangeEvent, session: Session | null) => {
      if (!session) {
        window.location.replace("/?auth=login");
      }
    });

    return () => {
      mounted = false;
      data.subscription.unsubscribe();
    };
  }, []);

  if (checking) {
    return <main className="auth-loading">Checking your session...</main>;
  }

  return <>{children}</>;
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, getUser, canUseEdAgent } from "@/lib/auth";

export function CuratorGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!canUseEdAgent(getUser())) {
      router.replace("/catalog");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        Проверка доступа…
      </div>
    );
  }

  return <>{children}</>;
}

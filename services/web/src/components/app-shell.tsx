"use client";

import type { ReactNode } from "react";
import clsx from "clsx";

type Props = {
  sidebar: ReactNode;
  children: ReactNode;
  className?: string;
  mainClassName?: string;
  /** Chat: main column does not scroll; inner area scrolls */
  contained?: boolean;
};

export function AppShell({
  sidebar,
  children,
  className,
  mainClassName,
  contained = false,
}: Props) {
  return (
    <div
      className={clsx(
        "flex h-dvh max-h-dvh overflow-hidden flex-col md:flex-row",
        className,
      )}
    >
      {sidebar}
      <main
        className={clsx(
          contained
            ? "flex min-h-0 flex-1 flex-col overflow-hidden"
            : "min-h-0 flex-1 overflow-y-auto overscroll-contain",
          mainClassName,
        )}
      >
        {children}
      </main>
    </div>
  );
}

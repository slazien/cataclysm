"use client";

import { useState } from "react";

interface ExpandableProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  titleColor?: string;
}

export default function Expandable({
  title,
  defaultOpen = false,
  children,
  titleColor,
}: ExpandableProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)]">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left cursor-pointer hover:bg-[var(--bg-secondary)] transition-colors rounded-lg"
      >
        <span
          className="text-sm font-semibold"
          style={{ color: titleColor ?? "var(--text-primary)" }}
        >
          {title}
        </span>
        <svg
          className={`h-4 w-4 text-[var(--text-secondary)] transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="border-t border-[var(--border-color)] px-4 py-3">{children}</div>}
    </div>
  );
}

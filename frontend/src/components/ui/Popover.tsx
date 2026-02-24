"use client";

import { useState, useRef } from "react";

interface PopoverProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
}

export default function Popover({ trigger, children }: PopoverProps) {
  const [show, setShow] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setShow(true);
  };

  const handleLeave = () => {
    timeoutRef.current = setTimeout(() => setShow(false), 150);
  };

  return (
    <div className="relative inline-block" onMouseEnter={handleEnter} onMouseLeave={handleLeave}>
      {trigger}
      {show && (
        <div className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-xs text-[var(--text-secondary)] shadow-lg whitespace-normal max-w-xs">
          {children}
        </div>
      )}
    </div>
  );
}

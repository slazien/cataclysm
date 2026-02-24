"use client";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeMap = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-10 w-10" };

export default function Spinner({ size = "md", className = "" }: SpinnerProps) {
  return (
    <div
      className={`animate-spin rounded-full border-2 border-[var(--border-color)] border-t-[var(--accent-blue)] ${sizeMap[size]} ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}

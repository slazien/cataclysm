'use client';

import React from 'react';

interface KingBadgeProps {
  size?: 'sm' | 'md';
}

/**
 * Crown badge displayed next to the current "King of the Corner".
 * Uses an inline SVG crown icon with a gold color scheme.
 */
export function KingBadge({ size = 'sm' }: KingBadgeProps) {
  const px = size === 'sm' ? 16 : 20;

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-yellow-500/20 px-1.5 py-0.5 text-yellow-400"
      title="King of the Corner"
    >
      <svg
        width={px}
        height={px}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
      >
        <path
          d="M5 16L3 6L8 10L12 4L16 10L21 6L19 16H5Z"
          fill="currentColor"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <rect
          x="5"
          y="17"
          width="14"
          height="3"
          rx="1"
          fill="currentColor"
        />
      </svg>
      {size === 'md' && (
        <span className="text-xs font-semibold">King</span>
      )}
    </span>
  );
}

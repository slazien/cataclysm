"use client";

import { forwardRef } from "react";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, options, className = "", ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label className="text-xs font-medium text-[var(--text-secondary)]">
            {label}
          </label>
        )}
        <select
          ref={ref}
          className={`
            w-full rounded-md border border-[var(--border-color)]
            bg-[var(--bg-card)] px-3 py-1.5 text-sm text-[var(--text-primary)]
            outline-none transition-colors
            focus:border-[var(--accent-blue)]
            ${className}
          `}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    );
  },
);
Select.displayName = "Select";

export default Select;

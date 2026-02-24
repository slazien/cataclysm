"use client";

import { forwardRef } from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
}

const variantClasses: Record<string, string> = {
  primary:
    "bg-[var(--accent-blue)] hover:bg-[#4090ef] text-white",
  secondary:
    "bg-[var(--bg-card)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)]",
  danger:
    "bg-[var(--accent-red)] hover:bg-[#e04440] text-white",
  ghost:
    "bg-transparent hover:bg-[var(--bg-card)] text-[var(--text-secondary)]",
};

const sizeClasses: Record<string, string> = {
  sm: "px-2.5 py-1 text-xs",
  md: "px-3.5 py-1.5 text-sm",
  lg: "px-5 py-2.5 text-base",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", className = "", disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={`
          inline-flex items-center justify-center rounded-md font-medium
          transition-colors duration-150 cursor-pointer
          disabled:opacity-50 disabled:cursor-not-allowed
          ${variantClasses[variant]}
          ${sizeClasses[size]}
          ${className}
        `}
        {...props}
      >
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";

export default Button;

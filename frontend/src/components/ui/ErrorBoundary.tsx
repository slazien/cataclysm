"use client";

import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Chart error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div
            className="flex items-center justify-center rounded-lg p-8"
            style={{ background: "var(--bg-card)" }}
          >
            <div className="text-center">
              <p className="font-medium text-[var(--accent-red)]">Something went wrong</p>
              <p className="mt-1 text-sm text-[var(--text-muted)]">
                {this.state.error?.message}
              </p>
              <button
                onClick={() => this.setState({ hasError: false })}
                className="mt-3 rounded bg-[var(--bg-secondary)] px-4 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--border-color)]"
              >
                Try Again
              </button>
            </div>
          </div>
        )
      );
    }
    return this.props.children;
  }
}

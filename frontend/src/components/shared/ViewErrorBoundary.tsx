'use client';

import React from 'react';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ViewErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ViewErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
          <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 text-center">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              Something went wrong
            </h2>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">
              This view encountered an error. Try going back to the dashboard.
            </p>
            <div className="mt-4 flex justify-center gap-2">
              <button
                onClick={() => this.setState({ hasError: false, error: null })}
                className="rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-4 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-surface)]"
              >
                Retry
              </button>
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.href = '/';
                }}
                className="rounded-md bg-[var(--cata-accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90"
              >
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

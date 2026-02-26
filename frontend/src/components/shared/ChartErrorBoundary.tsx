'use client';

import React from 'react';

interface Props {
  children: React.ReactNode;
  name?: string;
}

interface State {
  hasError: boolean;
}

export class ChartErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(
      `[ChartErrorBoundary${this.props.name ? `: ${this.props.name}` : ''}]`,
      error,
      info.componentStack,
    );
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full min-h-[100px] flex-col items-center justify-center gap-2 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <p className="text-xs text-[var(--text-muted)]">
            {this.props.name ? `${this.props.name} failed to render` : 'Chart failed to render'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-surface)]"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

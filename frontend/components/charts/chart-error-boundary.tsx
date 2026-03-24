"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ChartErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ChartErrorBoundary] Chart rendering failed:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="flex h-full min-h-[200px] items-center justify-center rounded-lg border border-border bg-surface p-6">
          <div className="text-center">
            <p className="mb-1 text-sm font-medium text-muted-foreground">
              Chart failed to render
            </p>
            <p className="text-xs text-muted-foreground/70">
              {this.state.error?.message ?? "An unexpected error occurred"}
            </p>
            <button
              className="mt-3 rounded-md bg-surface-raised px-3 py-1.5 text-xs text-foreground hover:bg-surface-raised/80"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              Retry
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

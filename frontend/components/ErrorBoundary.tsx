"use client";
import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: (err: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

/** 给页面级容器用：组件树抛错时不白屏，给一个能重试的兜底。 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }): void {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary] caught:", error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);
    return (
      <div className="bg-red-950/50 border border-red-700 rounded-xl p-5 m-4 text-sm">
        <h3 className="font-semibold text-red-200 mb-2">页面渲染出错了</h3>
        <p className="text-red-100/80 mb-2">{error.message || String(error)}</p>
        <details className="text-[11px] opacity-60 mb-3">
          <summary className="cursor-pointer">看完整堆栈</summary>
          <pre className="whitespace-pre-wrap mt-2">{error.stack}</pre>
        </details>
        <button
          onClick={this.reset}
          className="px-3 py-1.5 text-xs bg-red-600 hover:bg-red-500 rounded font-semibold"
        >重试渲染</button>
      </div>
    );
  }
}

import { Component, type ReactNode } from "react";

type Props = { message: string; retryLabel: string; children: ReactNode };
type State = { failed: boolean };

/** A screen that crashes shows a kind message instead of a blank page. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("screen error", error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-lg bg-amber-50 p-4 text-amber-900">
        <p>{this.props.message}</p>
        <button type="button" className="font-semibold underline" onClick={() => this.setState({ failed: false })}>
          {this.props.retryLabel}
        </button>
      </div>
    );
  }
}

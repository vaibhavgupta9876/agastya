import "./ErrorView.css";

interface Props {
  message: string;
  onReset: () => void;
}

export default function ErrorView({ message, onReset }: Props) {
  return (
    <main className="view error">
      <p className="error__label">Something didn’t quite work</p>
      <p className="error__message">{message}</p>
      <button className="error__back" onClick={onReset}>
        ← try again
      </button>
    </main>
  );
}

import { FormEvent, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { askAssistant } from "../../api/assistant";
import { errorMessage } from "../../api/client";
import { ErrorBanner } from "../../components/ui";

interface Props {
  courseId: string;
}

interface Turn {
  question: string;
  answer: string;
}

export default function AssistantPanel({ courseId }: Props) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || streaming) return;

    setError(null);
    setQuestion("");
    // Push the turn with an empty answer; we'll fill it as tokens stream in.
    const idx = turns.length;
    setTurns((prev) => [...prev, { question: q, answer: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await askAssistant(
        courseId,
        q,
        (token) =>
          setTurns((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], answer: next[idx].answer + token };
            return next;
          }),
        controller.signal,
      );
    } catch (err) {
      setError(errorMessage(err, "The assistant is unavailable right now"));
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const stop = () => abortRef.current?.abort();

  return (
    <section className="panel assistant-panel">
      <h2 className="panel-title">Ask this course</h2>
      <p className="muted small">
        Answers come only from this course's lessons (text, PDFs, and video
        transcripts). It will say so if a topic isn't covered.
      </p>

      <ErrorBanner message={error} />

      <div className="assistant-thread">
        {turns.length === 0 && (
          <p className="muted small assistant-empty">
            e.g. "What is the dangerous quest?" or "Summarize lesson 1."
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} className="assistant-turn">
            <div className="assistant-q">{t.question}</div>
            <div className="assistant-a">
              {t.answer ? (
                <ReactMarkdown>{t.answer}</ReactMarkdown>
              ) : (
                <span className="muted small">thinking…</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={onSubmit} className="assistant-form">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about this course…"
          disabled={streaming}
        />
        {streaming ? (
          <button type="button" className="btn btn-ghost" onClick={stop}>
            Stop
          </button>
        ) : (
          <button className="btn btn-primary" disabled={!question.trim()}>
            Ask
          </button>
        )}
      </form>
    </section>
  );
}

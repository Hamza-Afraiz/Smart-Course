import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { errorMessage } from "../../api/client";
import { generateContent, type GenerationKind } from "../../api/generation";
import type { Lesson } from "../../api/types";
import { ErrorBanner } from "../../components/ui";

interface Props {
  courseId: string;
  lessons: Lesson[];
}

export default function GenerationPanel({ courseId, lessons }: Props) {
  const [lessonId, setLessonId] = useState<string>("");
  const [output, setOutput] = useState("");
  const [kind, setKind] = useState<GenerationKind | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const run = async (selected: GenerationKind) => {
    if (streaming) return;
    setError(null);
    setOutput("");
    setKind(selected);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await generateContent(
        courseId,
        selected,
        (token) => setOutput((prev) => prev + token),
        {
          lessonId: lessonId || undefined,
          signal: controller.signal,
        },
      );
    } catch (err) {
      setError(errorMessage(err, "Generation is unavailable right now"));
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const stop = () => abortRef.current?.abort();

  return (
    <section className="panel assistant-panel">
      <h2 className="panel-title">Instructor tools</h2>
      <p className="muted small">
        Generate a summary or quiz from indexed lesson content (available after
        the course has been published at least once).
      </p>

      <ErrorBanner message={error} />

      <div className="inline-form" style={{ marginTop: "0.75rem" }}>
        <label htmlFor="gen-lesson">Scope</label>
        <select
          id="gen-lesson"
          value={lessonId}
          onChange={(e) => setLessonId(e.target.value)}
          disabled={streaming}
        >
        <option value="">Whole course</option>
        {lessons.map((l) => (
          <option key={l.id} value={l.id}>
            {l.title}
          </option>
        ))}
        </select>
      </div>

      <div className="btn-row" style={{ marginTop: "0.75rem" }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={streaming}
          onClick={() => run("summary")}
        >
          {streaming && kind === "summary" ? "Generating…" : "Generate summary"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={streaming}
          onClick={() => run("quiz")}
        >
          {streaming && kind === "quiz" ? "Generating…" : "Generate quiz"}
        </button>
        {streaming && (
          <button type="button" className="btn btn-ghost" onClick={stop}>
            Stop
          </button>
        )}
      </div>

      {(output || streaming) && (
        <div className="assistant-a generation-output">
          {output ? (
            <ReactMarkdown>{output}</ReactMarkdown>
          ) : (
            <span className="muted small">thinking…</span>
          )}
        </div>
      )}
    </section>
  );
}

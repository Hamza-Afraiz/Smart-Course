import { FormEvent, useState } from "react";
import { createLesson, createModule } from "../../api/courses";
import { errorMessage } from "../../api/client";
import type { ContentType, Lesson, Module } from "../../api/types";
import { ErrorBanner } from "../../components/ui";

interface Props {
  courseId: string;
  // null → render the "add module" form. set → render the "add lesson" form
  // for that module.
  module: Module | null;
  lessonCount: number;
  nextModuleIndex?: number;
  onModuleCreated?: (module: Module) => void;
  onLessonCreated?: (lesson: Lesson) => void;
}

const CONTENT_TYPES: ContentType[] = ["video", "text", "pdf"];

export default function ModuleManager({
  courseId,
  module,
  lessonCount,
  nextModuleIndex = 0,
  onModuleCreated,
  onLessonCreated,
}: Props) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [contentType, setContentType] = useState<ContentType>("video");
  const [contentUrl, setContentUrl] = useState("");
  const [duration, setDuration] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isModuleForm = module === null;

  const reset = () => {
    setTitle("");
    setContentUrl("");
    setDuration("");
    setError(null);
    setOpen(false);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (isModuleForm) {
        // order_index must be unique per course — next slot after the last one.
        const created = await createModule(courseId, {
          title: title.trim(),
          order_index: nextModuleIndex,
        });
        onModuleCreated?.(created);
      } else {
        const created = await createLesson(courseId, module.id, {
          title: title.trim(),
          order_index: lessonCount,
          content_type: contentType,
          content_url: contentUrl.trim() || undefined,
          duration_seconds: duration ? Number(duration) : undefined,
        });
        onLessonCreated?.(created);
      }
      reset();
    } catch (err) {
      setError(
        errorMessage(
          err,
          isModuleForm ? "Could not add module" : "Could not add lesson",
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        className={`btn btn-small btn-ghost ${isModuleForm ? "add-module-btn" : "add-lesson-btn"}`}
        onClick={() => setOpen(true)}
      >
        {isModuleForm ? "+ Add module" : "+ Add lesson"}
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="inline-form">
      <ErrorBanner message={error} />
      <div className="inline-form-row">
        <input
          className="grow"
          placeholder={isModuleForm ? "Module title" : "Lesson title"}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          maxLength={255}
          autoFocus
        />
        {!isModuleForm && (
          <>
            <select
              value={contentType}
              onChange={(e) => setContentType(e.target.value as ContentType)}
            >
              {CONTENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={0}
              placeholder="duration (s)"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              className="narrow"
            />
          </>
        )}
      </div>
      {!isModuleForm && (
        <input
          placeholder="Content URL (optional)"
          value={contentUrl}
          onChange={(e) => setContentUrl(e.target.value)}
          maxLength={1000}
        />
      )}
      <div className="inline-form-row">
        <button className="btn btn-small btn-primary" disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          className="btn btn-small btn-ghost"
          onClick={reset}
          disabled={busy}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

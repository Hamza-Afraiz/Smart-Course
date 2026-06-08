import { FormEvent, useState } from "react";
import { createLesson, createModule } from "../../api/courses";
import { uploadFile } from "../../api/uploads";
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
type SourceMode = "url" | "upload";

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
  const [sourceMode, setSourceMode] = useState<SourceMode>("url");
  const [contentUrl, setContentUrl] = useState("");
  const [contentText, setContentText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [duration, setDuration] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isModuleForm = module === null;
  const isText = contentType === "text";
  const isUpload = !isText && sourceMode === "upload";

  const reset = () => {
    setTitle("");
    setContentUrl("");
    setContentText("");
    setFile(null);
    setUploadPct(null);
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
        const created = await createModule(courseId, {
          title: title.trim(),
          order_index: nextModuleIndex,
        });
        onModuleCreated?.(created);
      } else {
        // Resolve the content source based on type + mode.
        let storage_key: string | undefined;
        let mime_type: string | undefined;
        let file_size: number | undefined;
        let content_url: string | undefined;
        let content_text: string | undefined;

        if (isText) {
          content_text = contentText.trim() || undefined;
        } else if (sourceMode === "upload") {
          if (!file) throw new Error("Choose a file to upload");
          setUploadPct(0);
          storage_key = await uploadFile(file, setUploadPct);
          mime_type = file.type || undefined;
          file_size = file.size;
        } else {
          content_url = contentUrl.trim() || undefined;
        }

        const created = await createLesson(courseId, module.id, {
          title: title.trim(),
          order_index: lessonCount,
          content_type: contentType,
          content_url,
          content_text,
          storage_key,
          mime_type,
          file_size,
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
      setUploadPct(null);
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
        )}
        {!isModuleForm && contentType === "video" && (
          <input
            type="number"
            min={0}
            placeholder="duration (s)"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            className="narrow"
          />
        )}
      </div>

      {/* ── Content source, varies by type ──────────────────────────── */}
      {!isModuleForm && isText && (
        <textarea
          placeholder="Lesson text (markdown supported)"
          value={contentText}
          onChange={(e) => setContentText(e.target.value)}
          rows={5}
        />
      )}

      {!isModuleForm && !isText && (
        <>
          <div className="inline-form-row source-toggle">
            <button
              type="button"
              className={`btn btn-small ${sourceMode === "url" ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setSourceMode("url")}
            >
              Link URL
            </button>
            <button
              type="button"
              className={`btn btn-small ${sourceMode === "upload" ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setSourceMode("upload")}
            >
              Upload file
            </button>
          </div>

          {sourceMode === "url" ? (
            <input
              placeholder={
                contentType === "video"
                  ? "YouTube / direct .mp4 URL"
                  : "PDF URL"
              }
              value={contentUrl}
              onChange={(e) => setContentUrl(e.target.value)}
              maxLength={1000}
            />
          ) : (
            <div className="upload-field">
              <input
                type="file"
                accept={contentType === "video" ? "video/*" : "application/pdf"}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              {uploadPct !== null && (
                <div className="upload-progress">
                  <div
                    className="upload-progress-fill"
                    style={{ width: `${uploadPct}%` }}
                  />
                  <span className="small muted">{uploadPct}%</span>
                </div>
              )}
            </div>
          )}
        </>
      )}

      <div className="inline-form-row">
        <button className="btn btn-small btn-primary" disabled={busy}>
          {busy
            ? isUpload && uploadPct !== null
              ? `Uploading ${uploadPct}%…`
              : "Saving…"
            : "Save"}
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

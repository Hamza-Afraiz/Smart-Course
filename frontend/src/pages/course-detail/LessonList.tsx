import { useState } from "react";
import type { Lesson } from "../../api/types";
import LessonPlayer from "./LessonPlayer";

interface Props {
  lessons: Lesson[];
  completedLessonIds: Set<string>;
  canComplete: boolean;
  onComplete: (lessonId: string) => void;
}

function formatDuration(seconds: number | null): string | null {
  if (!seconds) return null;
  const mins = Math.round(seconds / 60);
  return `${mins} min`;
}

function hasContent(lesson: Lesson): boolean {
  return !!(lesson.content_text || lesson.content_url);
}

export default function LessonList({
  lessons,
  completedLessonIds,
  canComplete,
  onComplete,
}: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (lessons.length === 0) {
    return <p className="muted small lesson-empty">No lessons in this module.</p>;
  }

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <ul className="lesson-list">
      {lessons.map((lesson) => {
        const done = completedLessonIds.has(lesson.id);
        const duration = formatDuration(lesson.duration_seconds);
        const isOpen = expanded.has(lesson.id);
        const playable = hasContent(lesson);

        return (
          <li key={lesson.id} className={`lesson-row ${done ? "is-done" : ""} ${isOpen ? "is-open" : ""}`}>
            <div className="lesson-row-header">
              <button
                type="button"
                className="lesson-toggle"
                onClick={() => toggle(lesson.id)}
                aria-expanded={isOpen}
                title={playable ? (isOpen ? "Collapse" : "Open lesson") : "No content yet"}
              >
                <span className="lesson-check">{done ? "✓" : "○"}</span>
                <span className="lesson-main">
                  <span className="lesson-title">{lesson.title}</span>
                  <span className="lesson-meta muted small">
                    {lesson.content_type ?? "lesson"}
                    {duration ? ` · ${duration}` : ""}
                    {!playable && " · empty"}
                  </span>
                </span>
                <span className="lesson-chevron" aria-hidden>
                  {isOpen ? "▾" : "▸"}
                </span>
              </button>
              {canComplete &&
                (done ? (
                  <span className="badge badge-green">Completed</span>
                ) : (
                  <button
                    className="btn btn-small btn-primary"
                    onClick={() => onComplete(lesson.id)}
                  >
                    Mark complete
                  </button>
                ))}
            </div>

            {isOpen && (
              <div className="lesson-row-body">
                <LessonPlayer lesson={lesson} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

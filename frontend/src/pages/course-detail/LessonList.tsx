import type { Lesson } from "../../api/types";

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

export default function LessonList({
  lessons,
  completedLessonIds,
  canComplete,
  onComplete,
}: Props) {
  if (lessons.length === 0) {
    return <p className="muted small lesson-empty">No lessons in this module.</p>;
  }

  return (
    <ul className="lesson-list">
      {lessons.map((lesson) => {
        const done = completedLessonIds.has(lesson.id);
        const duration = formatDuration(lesson.duration_seconds);
        return (
          <li key={lesson.id} className={`lesson-row ${done ? "is-done" : ""}`}>
            <span className="lesson-check">{done ? "✓" : "○"}</span>
            <span className="lesson-main">
              <span className="lesson-title">{lesson.title}</span>
              <span className="lesson-meta muted small">
                {lesson.content_type ?? "lesson"}
                {duration ? ` · ${duration}` : ""}
              </span>
            </span>
            {lesson.content_url && (
              <a
                href={lesson.content_url}
                target="_blank"
                rel="noreferrer"
                className="lesson-link"
              >
                Open
              </a>
            )}
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
          </li>
        );
      })}
    </ul>
  );
}

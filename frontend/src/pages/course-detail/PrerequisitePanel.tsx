import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  addPrerequisite,
  listPrerequisites,
  removePrerequisite,
} from "../../api/prerequisites";
import { listPublished } from "../../api/courses";
import { errorMessage } from "../../api/client";
import type { Course, PrerequisiteCourse } from "../../api/types";
import { ErrorBanner } from "../../components/ui";

interface Props {
  courseId: string;
  isOwner: boolean;
  isStudent: boolean;
  // course_ids the student has completed — used to badge each prereq met/unmet
  completedCourseIds: Set<string>;
}

export default function PrerequisitePanel({
  courseId,
  isOwner,
  isStudent,
  completedCourseIds,
}: Props) {
  const [prereqs, setPrereqs] = useState<PrerequisiteCourse[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [adding, setAdding] = useState(false);
  const [candidates, setCandidates] = useState<Course[]>([]);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setPrereqs(await listPrerequisites(courseId));
    } catch (err) {
      setError(errorMessage(err, "Could not load prerequisites"));
    } finally {
      setLoaded(true);
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  const openAdd = async () => {
    setAdding(true);
    setError(null);
    try {
      const published = await listPublished();
      setCandidates(published.filter((c) => c.id !== courseId));
    } catch (err) {
      setError(errorMessage(err, "Could not load courses"));
    }
  };

  const handleAdd = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      setPrereqs(await addPrerequisite(courseId, selected));
      setSelected("");
      setAdding(false);
    } catch (err) {
      // surfaces the backend's 409 "would create a cycle" / 422 messages
      setError(errorMessage(err, "Could not add prerequisite"));
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async (prereqId: string) => {
    setBusy(true);
    setError(null);
    try {
      await removePrerequisite(courseId, prereqId);
      setPrereqs((prev) => prev.filter((p) => p.id !== prereqId));
    } catch (err) {
      setError(errorMessage(err, "Could not remove prerequisite"));
    } finally {
      setBusy(false);
    }
  };

  if (!loaded) return null;
  // a student/visitor with no prerequisites doesn't need this panel at all
  if (!isOwner && prereqs.length === 0) return null;

  const alreadyIds = new Set(prereqs.map((p) => p.id));
  const selectable = candidates.filter((c) => !alreadyIds.has(c.id));

  return (
    <section className="panel">
      <h2 className="panel-title">Prerequisites</h2>
      {isStudent && prereqs.length > 0 && (
        <p className="muted small">
          Complete these courses before you can enroll.
        </p>
      )}
      <ErrorBanner message={error} />

      {prereqs.length === 0 ? (
        <p className="muted">No prerequisites — anyone can enroll.</p>
      ) : (
        <ul className="prereq-list">
          {prereqs.map((p) => {
            const met = completedCourseIds.has(p.id);
            return (
              <li key={p.id} className="prereq-item">
                <Link to={`/courses/${p.id}`}>{p.title}</Link>
                {isStudent && (
                  <span
                    className={`badge ${met ? "badge-green" : "badge-gray"}`}
                  >
                    {met ? "completed" : "required"}
                  </span>
                )}
                {isOwner && (
                  <button
                    className="btn btn-small btn-ghost"
                    onClick={() => handleRemove(p.id)}
                    disabled={busy}
                    title="Remove prerequisite"
                  >
                    ✕
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {isOwner &&
        (adding ? (
          <div className="control-row">
            <select
              className="grow"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">Select a course…</option>
              {selectable.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
            <button
              className="btn btn-small btn-primary"
              onClick={handleAdd}
              disabled={busy || !selected}
            >
              {busy ? "Adding…" : "Add"}
            </button>
            <button
              className="btn btn-small btn-ghost"
              onClick={() => {
                setAdding(false);
                setSelected("");
                setError(null);
              }}
              disabled={busy}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button className="btn btn-small btn-ghost" onClick={openAdd}>
            + Add prerequisite
          </button>
        ))}
    </section>
  );
}

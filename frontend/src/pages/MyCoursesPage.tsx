import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createCourse, listMine } from "../api/courses";
import { errorMessage } from "../api/client";
import type { Course } from "../api/types";
import { Badge, EmptyState, ErrorBanner, Spinner } from "../components/ui";

export default function MyCoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [maxStudents, setMaxStudents] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    listMine()
      .then(setCourses)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      const course = await createCourse({
        title: title.trim(),
        description: description.trim() || undefined,
        max_students: maxStudents ? Number(maxStudents) : undefined,
      });
      setCourses((prev) => [course, ...prev]);
      setTitle("");
      setDescription("");
      setMaxStudents("");
    } catch (err) {
      setCreateError(errorMessage(err, "Could not create course"));
    } finally {
      setCreating(false);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>My Courses</h1>
          <p className="muted">
            Every course you own — draft, published, and archived.
          </p>
        </div>
      </div>

      <ErrorBanner message={error} />

      <section className="panel">
        <h2 className="panel-title">Create a course</h2>
        <form onSubmit={handleCreate} className="form form-inline-grid">
          <ErrorBanner message={createError} />
          <label className="field">
            <span>Title</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={255}
            />
          </label>
          <label className="field">
            <span>Max students</span>
            <input
              type="number"
              min={1}
              value={maxStudents}
              onChange={(e) => setMaxStudents(e.target.value)}
              placeholder="unlimited"
            />
          </label>
          <label className="field field-wide">
            <span>Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </label>
          <button className="btn btn-primary" disabled={creating}>
            {creating ? "Creating…" : "Create course"}
          </button>
        </form>
      </section>

      {courses.length === 0 ? (
        <EmptyState>You haven't created any courses yet.</EmptyState>
      ) : (
        <div className="card-grid">
          {courses.map((course) => (
            <Link
              to={`/courses/${course.id}`}
              key={course.id}
              className="course-card"
            >
              <div className="course-card-body">
                <div className="course-card-title-row">
                  <h3>{course.title}</h3>
                  <Badge status={course.status} />
                </div>
                <p className="muted course-desc">
                  {course.description || "No description provided."}
                </p>
              </div>
              <div className="course-card-foot">
                <span className="muted small">
                  Created {new Date(course.created_at).toLocaleDateString()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

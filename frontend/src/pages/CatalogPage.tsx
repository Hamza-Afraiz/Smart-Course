import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listPublished } from "../api/courses";
import { listMyEnrollments } from "../api/enrollments";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Course } from "../api/types";
import { EmptyState, ErrorBanner, Spinner } from "../components/ui";

export default function CatalogPage() {
  const { user } = useAuth();
  const [courses, setCourses] = useState<Course[]>([]);
  const [enrolledIds, setEnrolledIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const published = await listPublished();
        // Students get an "Enrolled" marker — needs their enrollment list.
        const enrollments =
          user?.role === "student" ? await listMyEnrollments() : [];
        if (cancelled) return;
        setCourses(published);
        setEnrolledIds(new Set(enrollments.map((e) => e.course_id)));
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user?.role]);

  if (loading) return <Spinner />;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>Course Catalog</h1>
          <p className="muted">Published courses open for enrollment.</p>
        </div>
      </div>

      <ErrorBanner message={error} />

      {courses.length === 0 ? (
        <EmptyState>
          No published courses yet. Instructors can create and publish courses
          from <strong>My Courses</strong>.
        </EmptyState>
      ) : (
        <div className="card-grid">
          {courses.map((course) => (
            <Link
              to={`/courses/${course.id}`}
              key={course.id}
              className="course-card"
            >
              <div className="course-card-body">
                <h3>{course.title}</h3>
                <p className="muted course-desc">
                  {course.description || "No description provided."}
                </p>
              </div>
              <div className="course-card-foot">
                <span className="muted small">
                  {course.max_students
                    ? `Capacity: ${course.max_students}`
                    : "Unlimited seats"}
                </span>
                {enrolledIds.has(course.id) && (
                  <span className="badge badge-green">Enrolled</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

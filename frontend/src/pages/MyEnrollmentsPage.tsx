import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listMyEnrollments } from "../api/enrollments";
import { errorMessage } from "../api/client";
import type { EnrollmentWithCourse } from "../api/types";
import {
  Badge,
  EmptyState,
  ErrorBanner,
  ProgressBar,
  Spinner,
} from "../components/ui";

export default function MyEnrollmentsPage() {
  const [enrollments, setEnrollments] = useState<EnrollmentWithCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMyEnrollments()
      .then(setEnrollments)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>My Learning</h1>
          <p className="muted">Courses you're enrolled in and your progress.</p>
        </div>
      </div>

      <ErrorBanner message={error} />

      {enrollments.length === 0 ? (
        <EmptyState>
          You're not enrolled in anything yet. Browse the{" "}
          <Link to="/courses">catalog</Link> to get started.
        </EmptyState>
      ) : (
        <div className="enrollment-list">
          {enrollments.map((e) => (
            <Link
              to={`/courses/${e.course_id}`}
              key={e.id}
              className="enrollment-row"
            >
              <div className="enrollment-main">
                <div className="course-card-title-row">
                  <h3>{e.course_title}</h3>
                  <Badge status={e.status} />
                </div>
                <ProgressBar percent={e.progress_summary.percent} />
                <p className="muted small">
                  {e.progress_summary.completed_lessons} /{" "}
                  {e.progress_summary.total_lessons} lessons ·{" "}
                  {e.progress_summary.percent}%
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

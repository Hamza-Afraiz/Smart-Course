import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listMyCertificates } from "../api/certificates";
import { errorMessage } from "../api/client";
import type { Certificate } from "../api/types";
import { EmptyState, ErrorBanner, Spinner } from "../components/ui";

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

export default function MyCertificatesPage() {
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMyCertificates()
      .then(setCertificates)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>My Certificates</h1>
          <p className="muted">
            Earned when you complete every lesson in a course.
          </p>
        </div>
      </div>

      <ErrorBanner message={error} />

      {certificates.length === 0 ? (
        <EmptyState>
          No certificates yet. Finish all lessons in an enrolled course to earn
          one — start from{" "}
          <Link to="/my-enrollments">My Learning</Link>.
        </EmptyState>
      ) : (
        <div className="certificate-list">
          {certificates.map((cert) => (
            <article key={cert.id} className="certificate-card">
              <div className="certificate-badge" aria-hidden>
                ✓
              </div>
              <div className="certificate-body">
                <h2>{cert.course_title ?? "Course"}</h2>
                <p className="muted small">
                  Issued {formatDate(cert.issued_at)}
                </p>
                <Link
                  to={`/courses/${cert.course_id}`}
                  className="btn btn-ghost btn-small"
                >
                  View course
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

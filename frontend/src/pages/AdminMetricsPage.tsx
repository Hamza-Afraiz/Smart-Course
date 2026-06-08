import { useEffect, useState } from "react";
import * as metricsApi from "../api/metrics";
import { errorMessage } from "../api/client";
import type {
  CompletionMetrics,
  EnrollmentsTimeSeries,
  OverviewMetrics,
  PopularCourses,
  RecentActivity,
} from "../api/types";
import { ErrorBanner, Spinner } from "../components/ui";

interface Bundle {
  overview: OverviewMetrics;
  completion: CompletionMetrics;
  popular: PopularCourses;
  series: EnrollmentsTimeSeries;
  activity: RecentActivity;
}

function fmtPercent(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

function fmtDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m} min`;
  return `${(m / 60).toFixed(1)} h`;
}

function fmtRelativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

function fmtEventType(t: string): string {
  return t.replace(".", " · ");
}

export default function AdminMetricsPage() {
  const [data, setData] = useState<Bundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [overview, completion, popular, series, activity] = await Promise.all([
          metricsApi.getOverview(),
          metricsApi.getCompletion(),
          metricsApi.getPopularCourses(10),
          metricsApi.getEnrollmentsOverTime(30),
          metricsApi.getRecentActivity(15),
        ]);
        if (cancelled) return;
        setData({ overview, completion, popular, series, activity });
      } catch (err) {
        if (!cancelled) setError(errorMessage(err, "Failed to load metrics"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <Spinner />;
  if (error) {
    return (
      <div className="container">
        <ErrorBanner message={error} />
      </div>
    );
  }
  if (!data) return null;

  const seriesMax = Math.max(1, ...data.series.series.map((b) => b.count));

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>Platform metrics</h1>
          <p className="muted">
            Composed from PostgreSQL (current state) + MongoDB events log.
          </p>
        </div>
      </div>

      {/* ── Top stat cards ──────────────────────────────────────────── */}
      <section className="metrics-grid">
        <StatCard label="Students" value={data.overview.total_students} />
        <StatCard label="Instructors" value={data.overview.total_instructors} />
        <StatCard
          label="Courses published"
          value={data.overview.total_courses_published}
          sub={`${data.overview.total_courses_draft} drafts · ${data.overview.total_courses_archived} archived`}
        />
        <StatCard
          label="Enrollments"
          value={data.overview.total_enrollments}
          sub={`avg ${data.overview.avg_courses_per_student.toFixed(2)} / student`}
        />
        <StatCard
          label="Completion rate"
          value={fmtPercent(data.completion.completion_rate)}
          sub={`${data.completion.completed_enrollments} of ${data.completion.completed_enrollments + data.completion.active_enrollments}`}
        />
        <StatCard
          label="Avg time to complete"
          value={fmtDuration(data.completion.avg_completion_seconds)}
          sub="enrolled → all lessons done"
        />
      </section>

      {/* ── Popular courses + Recent activity side by side ─────────── */}
      <section className="metrics-row">
        <div className="panel">
          <h2 className="panel-title">Most popular courses</h2>
          {data.popular.courses.length === 0 ? (
            <p className="muted">No enrollments yet.</p>
          ) : (
            <ol className="popular-list">
              {data.popular.courses.map((c) => (
                <li key={c.course_id}>
                  <span className="popular-title">{c.title}</span>
                  <span className="popular-count">{c.enrollment_count}</span>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="panel">
          <h2 className="panel-title">Recent activity</h2>
          {data.activity.items.length === 0 ? (
            <p className="muted">No events yet.</p>
          ) : (
            <ul className="activity-list">
              {data.activity.items.map((it) => (
                <li key={it.event_key}>
                  <span className={`badge badge-event-${it.event_type.split(".")[0]}`}>
                    {fmtEventType(it.event_type)}
                  </span>
                  <span className="activity-meta muted small">
                    {fmtRelativeTime(it.archived_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* ── Enrollments over time — simple CSS bars ─────────────────── */}
      <section className="panel">
        <h2 className="panel-title">Enrollments per day (last 30 days)</h2>
        {data.series.series.length === 0 ? (
          <p className="muted">No enrollment events in this window.</p>
        ) : (
          <div className="bar-chart">
            {data.series.series.map((b) => (
              <div className="bar-col" key={b.date}>
                <div
                  className="bar-fill"
                  style={{ height: `${(b.count / seriesMax) * 100}%` }}
                  title={`${b.date}: ${b.count}`}
                />
                <span className="bar-count small muted">{b.count}</span>
                <span className="bar-date small muted">{b.date.slice(5)}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: number | string;
  sub?: string;
}) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub muted small">{sub}</div>}
    </div>
  );
}

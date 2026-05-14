import type { ReactNode } from "react";
import type { CourseStatus, EnrollmentStatus } from "../api/types";

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div className="page-center muted">{label}</div>;
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="banner banner-error">{message}</div>;
}

export function InfoBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="banner banner-info">{message}</div>;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

const STATUS_CLASS: Record<CourseStatus | EnrollmentStatus, string> = {
  draft: "badge-gray",
  published: "badge-green",
  archived: "badge-gray",
  active: "badge-blue",
  completed: "badge-green",
  dropped: "badge-gray",
};

export function Badge({ status }: { status: CourseStatus | EnrollmentStatus }) {
  return <span className={`badge ${STATUS_CLASS[status]}`}>{status}</span>;
}

export function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="progress-track" title={`${percent}%`}>
      <div className="progress-fill" style={{ width: `${Math.min(percent, 100)}%` }} />
    </div>
  );
}

import { api } from "./client";
import type {
  CompletionMetrics,
  EnrollmentsTimeSeries,
  OverviewMetrics,
  PopularCourses,
  RecentActivity,
} from "./types";

export async function getOverview(): Promise<OverviewMetrics> {
  const { data } = await api.get<OverviewMetrics>("/admin/metrics/overview");
  return data;
}

export async function getCompletion(): Promise<CompletionMetrics> {
  const { data } = await api.get<CompletionMetrics>("/admin/metrics/completion");
  return data;
}

export async function getPopularCourses(limit = 10): Promise<PopularCourses> {
  const { data } = await api.get<PopularCourses>("/admin/metrics/popular-courses", {
    params: { limit },
  });
  return data;
}

export async function getEnrollmentsOverTime(days = 30): Promise<EnrollmentsTimeSeries> {
  const { data } = await api.get<EnrollmentsTimeSeries>(
    "/admin/metrics/enrollments-over-time",
    { params: { days } },
  );
  return data;
}

export async function getRecentActivity(limit = 20): Promise<RecentActivity> {
  const { data } = await api.get<RecentActivity>("/admin/metrics/recent-activity", {
    params: { limit },
  });
  return data;
}

// Mirrors the Pydantic schemas in backend/app/schemas. Keep in sync by hand —
// the backend is the source of truth.

export type Role = "student" | "instructor" | "admin";
export type CourseStatus = "draft" | "published" | "archived";
export type ContentType = "video" | "text" | "pdf";
export type EnrollmentStatus = "active" | "completed" | "dropped";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Course {
  id: string;
  title: string;
  description: string | null;
  instructor_id: string;
  status: CourseStatus;
  max_students: number | null;
  processed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Module {
  id: string;
  course_id: string;
  title: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface Lesson {
  id: string;
  module_id: string;
  title: string;
  order_index: number;
  content_type: ContentType | null;
  content_url: string | null;
  content_text: string | null;
  storage_key: string | null;
  mime_type: string | null;
  // Resolved by the backend: presigned GET when uploaded, else content_url.
  playback_url: string | null;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
}

export interface UploadUrlResponse {
  upload_url: string;
  storage_key: string;
}

export interface ProgressSummary {
  total_lessons: number;
  completed_lessons: number;
  percent: number;
}

export interface Enrollment {
  id: string;
  student_id: string;
  course_id: string;
  status: EnrollmentStatus;
  enrolled_at: string;
  completed_at: string | null;
}

export interface EnrollmentWithCourse extends Enrollment {
  course_title: string;
  progress_summary: ProgressSummary;
}

export interface Progress {
  id: string;
  enrollment_id: string;
  lesson_id: string;
  completed_at: string;
}

export interface PublishAccepted {
  workflow_id: string;
}

export interface PublishStatus {
  workflow_id: string;
  status: string;
}

// ── Admin / Metrics ──────────────────────────────────────────────────────────

export interface OverviewMetrics {
  total_students: number;
  total_instructors: number;
  total_courses_published: number;
  total_courses_draft: number;
  total_courses_archived: number;
  total_enrollments: number;
  avg_courses_per_student: number;
}

export interface CompletionMetrics {
  completion_rate: number;
  avg_completion_seconds: number | null;
  completed_enrollments: number;
  active_enrollments: number;
}

export interface PopularCourse {
  course_id: string;
  title: string;
  enrollment_count: number;
}

export interface PopularCourses {
  courses: PopularCourse[];
}

export interface DayBucket {
  date: string; // YYYY-MM-DD
  count: number;
}

export interface EnrollmentsTimeSeries {
  series: DayBucket[];
}

export interface RecentActivityItem {
  event_type: string;
  event_key: string;
  archived_at: string;
  payload: Record<string, unknown>;
}

export interface RecentActivity {
  items: RecentActivityItem[];
}

// ── Semantic search (Week 4) ─────────────────────────────────────────────────

export interface SearchHit {
  lesson_id: string;
  lesson_title: string;
  course_id: string;
  course_title: string;
  chunk_index: number;
  text: string;
  similarity: number; // 0.0–1.0
}

export interface SearchResponse {
  query: string;
  results: SearchHit[];
}

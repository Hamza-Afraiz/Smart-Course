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
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
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

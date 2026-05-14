import { api } from "./client";
import type { Enrollment, EnrollmentWithCourse, Progress } from "./types";

export async function enroll(courseId: string): Promise<Enrollment> {
  const { data } = await api.post<Enrollment>(`/courses/${courseId}/enroll`);
  return data;
}

export async function listMyEnrollments(
  limit = 50,
  offset = 0,
): Promise<EnrollmentWithCourse[]> {
  const { data } = await api.get<EnrollmentWithCourse[]>("/enrollments/me", {
    params: { limit, offset },
  });
  return data;
}

export async function listProgress(enrollmentId: string): Promise<Progress[]> {
  const { data } = await api.get<Progress[]>(
    `/enrollments/${enrollmentId}/progress`,
  );
  return data;
}

export async function completeLesson(
  enrollmentId: string,
  lessonId: string,
): Promise<Progress> {
  const { data } = await api.post<Progress>(
    `/enrollments/${enrollmentId}/progress/${lessonId}`,
  );
  return data;
}

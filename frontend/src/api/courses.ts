import { api } from "./client";
import type {
  Course,
  Lesson,
  Module,
  PublishAccepted,
  PublishStatus,
} from "./types";

export async function listPublished(limit = 50, offset = 0): Promise<Course[]> {
  const { data } = await api.get<Course[]>("/courses", { params: { limit, offset } });
  return data;
}

export async function listMine(limit = 50, offset = 0): Promise<Course[]> {
  const { data } = await api.get<Course[]>("/courses/mine", {
    params: { limit, offset },
  });
  return data;
}

export async function getCourse(courseId: string): Promise<Course> {
  const { data } = await api.get<Course>(`/courses/${courseId}`);
  return data;
}

export async function createCourse(payload: {
  title: string;
  description?: string;
  max_students?: number;
}): Promise<Course> {
  const { data } = await api.post<Course>("/courses", payload);
  return data;
}

export async function archiveCourse(courseId: string): Promise<Course> {
  const { data } = await api.delete<Course>(`/courses/${courseId}`);
  return data;
}

export async function listModules(courseId: string): Promise<Module[]> {
  const { data } = await api.get<Module[]>(`/courses/${courseId}/modules`);
  return data;
}

export async function createModule(
  courseId: string,
  payload: { title: string; order_index: number },
): Promise<Module> {
  const { data } = await api.post<Module>(`/courses/${courseId}/modules`, payload);
  return data;
}

export async function listLessons(
  courseId: string,
  moduleId: string,
): Promise<Lesson[]> {
  const { data } = await api.get<Lesson[]>(
    `/courses/${courseId}/modules/${moduleId}/lessons`,
  );
  return data;
}

export async function createLesson(
  courseId: string,
  moduleId: string,
  payload: {
    title: string;
    order_index: number;
    content_type?: string;
    content_url?: string;
    content_text?: string;
    storage_key?: string;
    mime_type?: string;
    file_size?: number;
    duration_seconds?: number;
  },
): Promise<Lesson> {
  const { data } = await api.post<Lesson>(
    `/courses/${courseId}/modules/${moduleId}/lessons`,
    payload,
  );
  return data;
}

export async function publishCourse(courseId: string): Promise<PublishAccepted> {
  const { data } = await api.post<PublishAccepted>(`/courses/${courseId}/publish`);
  return data;
}

export async function getPublishStatus(courseId: string): Promise<PublishStatus> {
  const { data } = await api.get<PublishStatus>(`/courses/${courseId}/publish/status`);
  return data;
}

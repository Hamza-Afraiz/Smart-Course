import { api } from "./client";
import type { PrerequisiteCourse } from "./types";

export async function listPrerequisites(
  courseId: string,
): Promise<PrerequisiteCourse[]> {
  const { data } = await api.get<PrerequisiteCourse[]>(
    `/courses/${courseId}/prerequisites`,
  );
  return data;
}

export async function addPrerequisite(
  courseId: string,
  prerequisiteId: string,
): Promise<PrerequisiteCourse[]> {
  const { data } = await api.post<PrerequisiteCourse[]>(
    `/courses/${courseId}/prerequisites`,
    { prerequisite_id: prerequisiteId },
  );
  return data;
}

export async function removePrerequisite(
  courseId: string,
  prerequisiteId: string,
): Promise<void> {
  await api.delete(`/courses/${courseId}/prerequisites/${prerequisiteId}`);
}

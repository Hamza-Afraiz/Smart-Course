import { api } from "./client";
import type { CourseRecommendation } from "./types";

export async function getRecommendations(
  limit = 6,
): Promise<CourseRecommendation[]> {
  const { data } = await api.get<CourseRecommendation[]>(
    "/courses/recommendations",
    { params: { limit } },
  );
  return data;
}

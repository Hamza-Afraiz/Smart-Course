import { api } from "./client";
import type { SearchResponse } from "./types";

export async function semanticSearch(payload: {
  query: string;
  course_id?: string;
  limit?: number;
}): Promise<SearchResponse> {
  const { data } = await api.post<SearchResponse>("/search/semantic", payload);
  return data;
}

/** Search across only the courses the caller can access (backend-scoped). */
export async function searchMyCourses(payload: {
  query: string;
  limit?: number;
}): Promise<SearchResponse> {
  const { data } = await api.post<SearchResponse>("/search/my", payload);
  return data;
}

import { api } from "./client";
import type { Certificate } from "./types";

export async function listMyCertificates(
  limit = 50,
  offset = 0,
): Promise<Certificate[]> {
  const { data } = await api.get<Certificate[]>("/certificates/me", {
    params: { limit, offset },
  });
  return data;
}

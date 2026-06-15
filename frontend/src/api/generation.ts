import { tokenStore } from "./client";

const BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export type GenerationKind = "summary" | "quiz";

/**
 * Stream instructor content generation (summary or quiz). Same SSE framing as
 * askAssistant — tokens are JSON-encoded per frame.
 */
export async function generateContent(
  courseId: string,
  kind: GenerationKind,
  onToken: (t: string) => void,
  options?: { lessonId?: string; signal?: AbortSignal },
): Promise<void> {
  const resp = await fetch(`${BASE}/assistant/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${tokenStore.get()}`,
    },
    body: JSON.stringify({
      course_id: courseId,
      kind,
      lesson_id: options?.lessonId ?? null,
    }),
    signal: options?.signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Generation failed (HTTP ${resp.status})`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const data = line.slice(5).trim();
      if (data === "[DONE]") return;
      try {
        onToken(JSON.parse(data));
      } catch {
        // ignore malformed frame
      }
    }
  }
}

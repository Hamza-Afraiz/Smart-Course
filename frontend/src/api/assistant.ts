import { tokenStore } from "./client";

const BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

/**
 * Ask the course assistant. Streams the answer via SSE — calls `onToken` for
 * each text chunk as it arrives. Resolves when the stream completes.
 *
 * Uses fetch (not axios) because we need the streaming body reader; the JWT is
 * attached manually since the axios interceptor doesn't apply here.
 */
export async function askAssistant(
  courseId: string,
  question: string,
  onToken: (t: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${BASE}/assistant/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${tokenStore.get()}`,
    },
    body: JSON.stringify({ course_id: courseId, question }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Assistant request failed (HTTP ${resp.status})`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? ""; // keep the trailing partial frame

    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const data = line.slice(5).trim();
      if (data === "[DONE]") return;
      try {
        onToken(JSON.parse(data)); // tokens are JSON-encoded (handles newlines)
      } catch {
        // ignore malformed frame
      }
    }
  }
}

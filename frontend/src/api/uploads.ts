import { api } from "./client";
import type { UploadUrlResponse } from "./types";

/**
 * Upload a file straight to object storage:
 *   1. ask our API for a presigned PUT URL + storage_key
 *   2. PUT the bytes directly to that URL (bypasses our API)
 *   3. return the storage_key to attach to the lesson
 *
 * `onProgress` (0–100) drives an upload progress bar.
 */
export async function uploadFile(
  file: File,
  onProgress?: (pct: number) => void,
): Promise<string> {
  const { data } = await api.post<UploadUrlResponse>("/uploads", {
    filename: file.name,
    content_type: file.type || "application/octet-stream",
  });

  await putToPresignedUrl(data.upload_url, file, onProgress);
  return data.storage_key;
}

function putToPresignedUrl(
  url: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<void> {
  // XHR (not fetch) so we get upload progress events.
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Upload failed (HTTP ${xhr.status})`));
    xhr.onerror = () => reject(new Error("Upload failed (network error)"));
    xhr.send(file);
  });
}

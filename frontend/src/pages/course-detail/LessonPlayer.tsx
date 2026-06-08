import ReactMarkdown from "react-markdown";
import type { Lesson } from "../../api/types";

/** Lessons have ONE primary content type. Render accordingly. */
export default function LessonPlayer({ lesson }: { lesson: Lesson }) {
  if (lesson.content_type === "text") {
    if (!lesson.content_text) return <Empty />;
    return (
      <div className="lesson-player lesson-player-text">
        <ReactMarkdown>{lesson.content_text}</ReactMarkdown>
      </div>
    );
  }

  // For video/pdf, prefer the backend-resolved playback_url (presigned GET for
  // uploads, else the external content_url). Fall back to content_url.
  const src = lesson.playback_url || lesson.content_url;

  if (lesson.content_type === "video") {
    if (!src) return <Empty />;
    const embed = toEmbedUrl(src);
    // YouTube/Vimeo → iframe embed; direct/uploaded mp4 → <video>.
    if (embed) {
      return (
        <div className="lesson-player lesson-player-video">
          <iframe
            src={embed}
            title={lesson.title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      );
    }
    return (
      <div className="lesson-player lesson-player-video">
        <video src={src} controls />
      </div>
    );
  }

  if (lesson.content_type === "pdf") {
    if (!src) return <Empty />;
    return (
      <div className="lesson-player lesson-player-pdf">
        <iframe src={src} title={lesson.title} />
        <a href={src} target="_blank" rel="noreferrer" className="btn btn-small btn-ghost">
          Open PDF in new tab ↗
        </a>
      </div>
    );
  }

  return <Empty />;
}

function Empty() {
  return (
    <div className="lesson-player lesson-player-empty muted small">
      No content provided for this lesson yet.
    </div>
  );
}

/**
 * Convert a YouTube watch URL or a Vimeo URL into its embed form.
 * Returns null if the URL isn't recognised — caller can fall back to <video>.
 */
function toEmbedUrl(url: string): string | null {
  try {
    const u = new URL(url);
    // youtube.com/watch?v=ID
    if (u.hostname.includes("youtube.com") && u.searchParams.get("v")) {
      return `https://www.youtube.com/embed/${u.searchParams.get("v")}`;
    }
    // youtu.be/ID
    if (u.hostname === "youtu.be") {
      return `https://www.youtube.com/embed${u.pathname}`;
    }
    // youtube.com/embed/ID (already embed form)
    if (u.hostname.includes("youtube.com") && u.pathname.startsWith("/embed/")) {
      return url;
    }
    // vimeo.com/ID
    if (u.hostname === "vimeo.com") {
      return `https://player.vimeo.com/video${u.pathname}`;
    }
    return null;
  } catch {
    return null;
  }
}

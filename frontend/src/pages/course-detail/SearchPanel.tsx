import { FormEvent, useState } from "react";
import * as searchApi from "../../api/search";
import { errorMessage } from "../../api/client";
import type { SearchHit } from "../../api/types";
import { ErrorBanner } from "../../components/ui";

interface Props {
  courseId: string;
}

export default function SearchPanel({ courseId }: Props) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await searchApi.semanticSearch({
        query: query.trim(),
        course_id: courseId,
        limit: 5,
      });
      setHits(res.results);
    } catch (err) {
      setError(errorMessage(err, "Search failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="panel-title">Search this course</h2>
      <p className="muted small" style={{ marginTop: -8, marginBottom: 12 }}>
        Semantic search across every lesson — match by meaning, not just keywords.
      </p>

      <form onSubmit={onSubmit} className="search-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='e.g. "how do I scale Postgres replication"'
          disabled={loading}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !query.trim()}
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      <ErrorBanner message={error} />

      {hits !== null && hits.length === 0 && (
        <p className="muted small" style={{ marginTop: 12 }}>
          No relevant lessons found for that query — this course doesn't seem to
          cover it.
        </p>
      )}

      {hits && hits.length > 0 && (
        <ul className="search-hits">
          {hits.map((h) => (
            <li key={`${h.lesson_id}-${h.chunk_index}`} className="search-hit">
              <div className="search-hit-head">
                <span className="search-hit-title">{h.lesson_title}</span>
                <span
                  className="search-hit-score"
                  title={`cosine similarity ${h.similarity.toFixed(3)}`}
                >
                  {(h.similarity * 100).toFixed(0)}% match
                </span>
              </div>
              <p className="search-hit-text">{h.text}</p>
              <span className="muted small">chunk #{h.chunk_index}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

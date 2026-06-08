import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { searchMyCourses } from "../api/search";
import { errorMessage } from "../api/client";
import type { SearchHit } from "../api/types";
import { ErrorBanner } from "./ui";

/** Semantic search across the user's accessible courses (enrolled / owned).
 * Lives at the top of the Catalog page. Each hit links to its course. */
export default function GlobalSearch() {
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
      const res = await searchMyCourses({ query: query.trim(), limit: 8 });
      setHits(res.results);
    } catch (err) {
      setError(errorMessage(err, "Search failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="panel-title">Search your courses</h2>
      <p className="muted small">
        Semantic search across every course you're enrolled in — by meaning, not
        just keywords.
      </p>

      <form onSubmit={onSubmit} className="search-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='e.g. "how does enrollment handle capacity?"'
          disabled={loading}
        />
        <button className="btn btn-primary" disabled={loading || !query.trim()}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      <ErrorBanner message={error} />

      {hits !== null && hits.length === 0 && (
        <p className="muted small" style={{ marginTop: 12 }}>
          No matches in your enrolled courses for that query.
        </p>
      )}

      {hits && hits.length > 0 && (
        <ul className="search-hits">
          {hits.map((h) => (
            <li key={`${h.lesson_id}-${h.chunk_index}`} className="search-hit">
              <div className="search-hit-head">
                <Link to={`/courses/${h.course_id}`} className="search-hit-title">
                  {h.course_title} · {h.lesson_title}
                </Link>
                <span
                  className="search-hit-score"
                  title={`cosine similarity ${h.similarity.toFixed(3)}`}
                >
                  {(h.similarity * 100).toFixed(0)}% match
                </span>
              </div>
              <p className="search-hit-text">{h.text}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

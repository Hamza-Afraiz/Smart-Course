import { FormEvent, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { updateMe } from "../api/auth";
import { errorMessage } from "../api/client";
import { ErrorBanner, InfoBanner } from "../components/ui";

export default function ProfilePage() {
  const { user, refresh } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!user) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await updateMe({
        full_name: fullName.trim() || undefined,
        password: password || undefined,
      });
      await refresh();
      setPassword("");
      setNotice("Profile updated.");
    } catch (err) {
      setError(errorMessage(err, "Could not update profile"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container container-narrow">
      <div className="page-head">
        <div>
          <h1>Profile</h1>
          <p className="muted">Your account details.</p>
        </div>
      </div>

      <section className="panel">
        <dl className="detail-grid">
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Role</dt>
          <dd>
            <span className={`badge badge-role badge-${user.role}`}>
              {user.role}
            </span>
          </dd>
          <dt>Member since</dt>
          <dd>{new Date(user.created_at).toLocaleDateString()}</dd>
        </dl>
      </section>

      <section className="panel">
        <h2 className="panel-title">Update profile</h2>
        <form onSubmit={handleSubmit} className="form">
          <ErrorBanner message={error} />
          <InfoBanner message={notice} />
          <label className="field">
            <span>Full name</span>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              maxLength={255}
            />
          </label>
          <label className="field">
            <span>New password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="leave blank to keep current"
              minLength={8}
            />
          </label>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </button>
        </form>
      </section>
    </div>
  );
}

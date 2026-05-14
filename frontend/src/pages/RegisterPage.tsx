import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { register } from "../api/auth";
import { errorMessage } from "../api/client";
import type { Role } from "../api/types";
import { ErrorBanner } from "../components/ui";

export default function RegisterPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("student");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/courses" replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({
        email,
        password,
        role,
        full_name: fullName.trim() || undefined,
      });
      // Registration does not return a token — log in immediately after.
      await login(email, password);
      navigate("/courses", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Registration failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <h1 className="brand brand-lg">
          Smart<span>Course</span>
        </h1>
        <p className="muted">Create your account</p>

        <form onSubmit={handleSubmit} className="form">
          <ErrorBanner message={error} />
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </label>
          <label className="field">
            <span>Full name</span>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="optional"
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
            <small className="muted">At least 8 characters.</small>
          </label>
          <label className="field">
            <span>I am a…</span>
            <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="student">Student — enroll and learn</option>
              <option value="instructor">Instructor — create and publish courses</option>
            </select>
          </label>
          <button className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? "Creating…" : "Create account"}
          </button>
        </form>

        <p className="auth-foot muted">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}

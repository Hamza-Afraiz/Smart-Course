import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/courses" className="brand">
            Smart<span>Course</span>
          </NavLink>

          <nav className="nav-links">
            <NavLink to="/courses">Catalog</NavLink>
            {user?.role === "student" && (
              <NavLink to="/my-enrollments">My Learning</NavLink>
            )}
            {(user?.role === "instructor" || user?.role === "admin") && (
              <NavLink to="/my-courses">My Courses</NavLink>
            )}
            {user?.role === "admin" && (
              <NavLink to="/admin/metrics">Metrics</NavLink>
            )}
            <NavLink to="/profile">Profile</NavLink>
          </nav>

          {user && (
            <div className="topbar-user">
              <span className="user-meta">
                {user.full_name || user.email}
                <span className={`badge badge-role badge-${user.role}`}>
                  {user.role}
                </span>
              </span>
              <button className="btn btn-ghost" onClick={handleLogout}>
                Log out
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

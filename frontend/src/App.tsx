import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import CatalogPage from "./pages/CatalogPage";
import CourseDetailPage from "./pages/CourseDetailPage";
import MyCoursesPage from "./pages/MyCoursesPage";
import MyEnrollmentsPage from "./pages/MyEnrollmentsPage";
import MyCertificatesPage from "./pages/MyCertificatesPage";
import ProfilePage from "./pages/ProfilePage";
import AdminMetricsPage from "./pages/AdminMetricsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/courses" element={<CatalogPage />} />
        <Route path="/courses/:courseId" element={<CourseDetailPage />} />
        <Route
          path="/my-courses"
          element={
            <ProtectedRoute roles={["instructor", "admin"]}>
              <MyCoursesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/my-enrollments"
          element={
            <ProtectedRoute roles={["student"]}>
              <MyEnrollmentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/my-certificates"
          element={
            <ProtectedRoute roles={["student"]}>
              <MyCertificatesPage />
            </ProtectedRoute>
          }
        />
        <Route path="/profile" element={<ProfilePage />} />
        <Route
          path="/admin/metrics"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminMetricsPage />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="/" element={<Navigate to="/courses" replace />} />
      <Route path="*" element={<Navigate to="/courses" replace />} />
    </Routes>
  );
}

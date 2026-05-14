import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  archiveCourse,
  getCourse,
  getPublishStatus,
  listLessons,
  listModules,
  publishCourse,
} from "../api/courses";
import {
  completeLesson,
  enroll,
  listMyEnrollments,
  listProgress,
} from "../api/enrollments";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type {
  Course,
  EnrollmentWithCourse,
  Lesson,
  Module,
} from "../api/types";
import {
  Badge,
  ErrorBanner,
  InfoBanner,
  ProgressBar,
  Spinner,
} from "../components/ui";
import ModuleManager from "./course-detail/ModuleManager";
import LessonList from "./course-detail/LessonList";

export default function CourseDetailPage() {
  const { courseId = "" } = useParams();
  const { user } = useAuth();

  const [course, setCourse] = useState<Course | null>(null);
  const [modules, setModules] = useState<Module[]>([]);
  const [lessonsByModule, setLessonsByModule] = useState<
    Record<string, Lesson[]>
  >({});
  const [enrollment, setEnrollment] = useState<EnrollmentWithCourse | null>(null);
  const [completedLessonIds, setCompletedLessonIds] = useState<Set<string>>(
    new Set(),
  );

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [publishStatus, setPublishStatus] = useState<string | null>(null);

  const isOwner =
    !!course && !!user && (user.id === course.instructor_id || user.role === "admin");
  const isStudent = user?.role === "student";

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const fetchedCourse = await getCourse(courseId);
      const fetchedModules = await listModules(courseId);
      const lessonEntries = await Promise.all(
        fetchedModules.map(
          async (m) => [m.id, await listLessons(courseId, m.id)] as const,
        ),
      );

      let myEnrollment: EnrollmentWithCourse | null = null;
      let completed = new Set<string>();
      if (user?.role === "student") {
        const enrollments = await listMyEnrollments();
        myEnrollment =
          enrollments.find((e) => e.course_id === courseId) ?? null;
        if (myEnrollment) {
          const progress = await listProgress(myEnrollment.id);
          completed = new Set(progress.map((p) => p.lesson_id));
        }
      }

      setCourse(fetchedCourse);
      setModules(fetchedModules);
      setLessonsByModule(Object.fromEntries(lessonEntries));
      setEnrollment(myEnrollment);
      setCompletedLessonIds(completed);
    } catch (err) {
      setError(errorMessage(err, "Could not load this course"));
    } finally {
      setLoading(false);
    }
  }, [courseId, user?.role]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Owners can peek at the Temporal publish workflow state. A 404 just means
  // no publish has ever been started for this course — not an error.
  const refreshPublishStatus = useCallback(async () => {
    try {
      const status = await getPublishStatus(courseId);
      setPublishStatus(status.status);
    } catch {
      setPublishStatus(null);
    }
  }, [courseId]);

  useEffect(() => {
    if (isOwner) refreshPublishStatus();
  }, [isOwner, refreshPublishStatus]);

  const handlePublish = async () => {
    setActionError(null);
    setNotice(null);
    setBusy(true);
    try {
      await publishCourse(courseId);
      setNotice(
        "Publish workflow started. Temporal is validating and processing the course — status updates below.",
      );
      // Poll the workflow a handful of times so the UI reflects completion.
      for (let i = 0; i < 8; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        await refreshPublishStatus();
      }
      await loadAll();
    } catch (err) {
      setActionError(errorMessage(err, "Publish failed"));
    } finally {
      setBusy(false);
    }
  };

  const handleArchive = async () => {
    if (!confirm("Archive this course? Students can no longer enroll.")) return;
    setActionError(null);
    setBusy(true);
    try {
      const updated = await archiveCourse(courseId);
      setCourse(updated);
      setNotice("Course archived.");
    } catch (err) {
      setActionError(errorMessage(err, "Archive failed"));
    } finally {
      setBusy(false);
    }
  };

  const handleEnroll = async () => {
    setActionError(null);
    setBusy(true);
    try {
      await enroll(courseId);
      await loadAll();
      setNotice("You're enrolled. Work through the lessons below.");
    } catch (err) {
      setActionError(errorMessage(err, "Enrollment failed"));
    } finally {
      setBusy(false);
    }
  };

  const handleCompleteLesson = async (lessonId: string) => {
    if (!enrollment) return;
    setActionError(null);
    try {
      await completeLesson(enrollment.id, lessonId);
      setCompletedLessonIds((prev) => new Set(prev).add(lessonId));
      // Completing the final lesson flips the enrollment to "completed" — refetch.
      const enrollments = await listMyEnrollments();
      setEnrollment(enrollments.find((e) => e.course_id === courseId) ?? null);
    } catch (err) {
      setActionError(errorMessage(err, "Could not mark lesson complete"));
    }
  };

  if (loading) return <Spinner />;
  if (error) {
    return (
      <div className="container">
        <ErrorBanner message={error} />
        <Link to="/courses" className="btn btn-ghost">
          ← Back to catalog
        </Link>
      </div>
    );
  }
  if (!course) return null;

  const totalLessons = Object.values(lessonsByModule).reduce(
    (sum, l) => sum + l.length,
    0,
  );

  return (
    <div className="container">
      <Link to="/courses" className="back-link">
        ← Catalog
      </Link>

      <div className="page-head">
        <div>
          <div className="course-card-title-row">
            <h1>{course.title}</h1>
            <Badge status={course.status} />
          </div>
          <p className="muted">
            {course.description || "No description provided."}
          </p>
        </div>
      </div>

      <InfoBanner message={notice} />
      <ErrorBanner message={actionError} />

      {/* ── Owner controls ─────────────────────────────────────────────── */}
      {isOwner && (
        <section className="panel">
          <h2 className="panel-title">Instructor controls</h2>
          <div className="control-row">
            {course.status === "draft" && (
              <button
                className="btn btn-primary"
                onClick={handlePublish}
                disabled={busy || totalLessons === 0}
                title={
                  totalLessons === 0
                    ? "Add at least one lesson before publishing"
                    : undefined
                }
              >
                {busy ? "Working…" : "Publish course"}
              </button>
            )}
            {course.status !== "archived" && (
              <button
                className="btn btn-danger"
                onClick={handleArchive}
                disabled={busy}
              >
                Archive
              </button>
            )}
            <button
              className="btn btn-ghost"
              onClick={refreshPublishStatus}
              disabled={busy}
            >
              Refresh publish status
            </button>
          </div>
          {totalLessons === 0 && course.status === "draft" && (
            <p className="muted small">
              A course needs at least one lesson before it can be published.
            </p>
          )}
          {publishStatus && (
            <p className="muted small">
              Publish workflow status: <strong>{publishStatus}</strong>
            </p>
          )}
        </section>
      )}

      {/* ── Student enrollment / progress ──────────────────────────────── */}
      {isStudent && (
        <section className="panel">
          {enrollment ? (
            <>
              <div className="course-card-title-row">
                <h2 className="panel-title">Your progress</h2>
                <Badge status={enrollment.status} />
              </div>
              <ProgressBar percent={enrollment.progress_summary.percent} />
              <p className="muted small">
                {enrollment.progress_summary.completed_lessons} of{" "}
                {enrollment.progress_summary.total_lessons} lessons completed (
                {enrollment.progress_summary.percent}%)
              </p>
            </>
          ) : (
            <>
              <h2 className="panel-title">Enroll in this course</h2>
              <p className="muted">
                {course.status === "published"
                  ? "Enroll to track your progress through the lessons."
                  : "This course is not open for enrollment."}
              </p>
              <button
                className="btn btn-primary"
                onClick={handleEnroll}
                disabled={busy || course.status !== "published"}
              >
                {busy ? "Enrolling…" : "Enroll"}
              </button>
            </>
          )}
        </section>
      )}

      {/* ── Curriculum ─────────────────────────────────────────────────── */}
      <section className="panel">
        <div className="course-card-title-row">
          <h2 className="panel-title">Curriculum</h2>
          <span className="muted small">
            {modules.length} modules · {totalLessons} lessons
          </span>
        </div>

        {modules.length === 0 && (
          <p className="muted">No modules yet.</p>
        )}

        {modules.map((module) => (
          <div key={module.id} className="module-block">
            <h3 className="module-title">
              <span className="module-index">{module.order_index + 1}</span>
              {module.title}
            </h3>
            <LessonList
              lessons={lessonsByModule[module.id] ?? []}
              completedLessonIds={completedLessonIds}
              canComplete={!!enrollment}
              onComplete={handleCompleteLesson}
            />
            {isOwner && (
              <ModuleManager
                courseId={courseId}
                module={module}
                lessonCount={(lessonsByModule[module.id] ?? []).length}
                onLessonCreated={(lesson) =>
                  setLessonsByModule((prev) => ({
                    ...prev,
                    [module.id]: [...(prev[module.id] ?? []), lesson],
                  }))
                }
              />
            )}
          </div>
        ))}

        {isOwner && (
          <ModuleManager
            courseId={courseId}
            module={null}
            lessonCount={0}
            nextModuleIndex={modules.length}
            onModuleCreated={(module) => {
              setModules((prev) => [...prev, module]);
              setLessonsByModule((prev) => ({ ...prev, [module.id]: [] }));
            }}
          />
        )}
      </section>
    </div>
  );
}

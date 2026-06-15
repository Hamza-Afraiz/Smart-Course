class SmartCourseError(Exception):
    """Base for all domain exceptions. Routers convert these to HTTPException."""


class EmailAlreadyExistsError(SmartCourseError):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"Email already registered: {email}")


class InvalidCredentialsError(SmartCourseError):
    pass


class UserNotFoundError(SmartCourseError):
    pass


class CourseNotFoundError(SmartCourseError):
    pass


class ModuleNotFoundError(SmartCourseError):
    pass


class LessonNotFoundError(SmartCourseError):
    pass


class OrderIndexConflictError(SmartCourseError):
    """Raised when trying to insert a module/lesson at an order_index already taken."""


class InvalidStatusTransitionError(SmartCourseError):
    pass


class ForbiddenError(SmartCourseError):
    pass


class AlreadyEnrolledError(SmartCourseError):
    """Raised when a student tries to enroll twice in the same course."""


class CourseNotPublishedError(SmartCourseError):
    """Raised when a student tries to enroll in a draft or archived course."""


class CourseFullError(SmartCourseError):
    """Raised when course capacity (max_students) is reached."""


class EnrollmentNotFoundError(SmartCourseError):
    pass


class LessonNotInCourseError(SmartCourseError):
    """Raised when a lesson does not belong to the course the enrollment is for."""


class InvalidPrerequisiteError(SmartCourseError):
    """Prerequisite target is invalid — self-reference or a nonexistent course."""


class PrerequisiteCycleError(SmartCourseError):
    """Adding this prerequisite would create a cycle in the requirement graph."""


class PrerequisitesNotMetError(SmartCourseError):
    """Student tried to enroll before completing required prerequisite courses."""

    def __init__(self, missing: list) -> None:
        self.missing = missing
        titles = ", ".join(c.title for c in missing)
        super().__init__(f"Complete required course(s) first: {titles}")


class TemporalUnavailableError(SmartCourseError):
    """Temporal client is not connected (e.g. server down or misconfigured)."""


class PublishWorkflowInProgressError(SmartCourseError):
    """Another publish workflow is already registered for this course_id."""


class WorkflowNotFoundError(SmartCourseError):
    """No Temporal workflow exists for the given workflow_id."""

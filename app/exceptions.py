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


class ForbiddenError(SmartCourseError):
    pass

"""
Core exceptions
"""


class NotFoundException(Exception):
    """Raised when an entity is not found in the database."""

    pass


class NotAuthorizedException(Exception):
    """Raised when a user is not authorized to perform an action."""

    pass


class ValidationError(Exception):
    """Raised when a user provides invalid data."""

    pass


"""
User exceptions
"""


class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user that already exists."""

    pass


class DuplicateUserError(Exception):
    """Raised when a user already exists in the database."""

    pass


"""
Feedback exceptions
"""


class InvalidFeedbackRatingError(Exception):
    """Raised when an invalid feedback rating is provided."""

    pass


class DuplicateFeedbackError(Exception):
    """Raised when a user tries to provide duplicate feedback."""

    pass


"""
Message exceptions
"""


class InvalidMessageTypeError(Exception):
    """Raised when an invalid message type is provided."""

    pass

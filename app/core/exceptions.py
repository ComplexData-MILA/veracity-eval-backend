class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user that already exists."""

    pass


class NotFoundException(Exception):
    """Raised when an entity is not found in the database."""

    pass


class NotAuthorizedException(Exception):
    """Raised when a user is not authorized to perform an action."""

    pass

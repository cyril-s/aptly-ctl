class AptlyCtlError(Exception):
    """Base class for exceptions in aptly_ctl module."""

    pass


class NotFoundError(AptlyCtlError):
    """
    Exception raised for errors in operations on entities that does not exist.

    Attributes:
        name -- name of an entity that was not found
    """

    entity_name = ""

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return (
            "{} '{}' not found".format(self.entity_name, self.name)
            .capitalize()
            .lstrip()
        )


class RepoNotFoundError(NotFoundError):
    entity_name = "local repo"


class SnapshotNotFoundError(NotFoundError):
    entity_name = "snapshot"


class PackageNotFoundError(NotFoundError):
    entity_name = "package"


class InvalidOperationError(AptlyCtlError):
    """
    Exception raised for errors in operations that connot be performed
    because of some conflicts that user must resolve

    Attributes:
        description -- of invalid operation
    """

    def __init__(self, description):
        self.description = description

    def __str__(self):
        return "Invalid operation: {}".format(self.description)

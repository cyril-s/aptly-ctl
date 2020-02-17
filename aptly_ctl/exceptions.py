import json
import typing
import http
import logging

logger = logging.getLogger(__name__)


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

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
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

    def __init__(self, description: str) -> None:
        self.description = description

    def __str__(self) -> str:
        return "Invalid operation: {}".format(self.description)


class AptlyApiError(AptlyCtlError):
    """
    Exception for aptly API errors
    """

    status: http.HTTPStatus
    errors: typing.Sequence[typing.Tuple[str, str]]
    msg: str

    def __str__(self) -> str:
        if not self.errors and not self.msg:
            return "{s.value} {s.phrase}".format(s=self.status)
        elif not self.errors:
            return "{s.value} {s.phrase}: {msg}".format(s=self.status, msg=self.msg)
        elif len(self.errors) == 1:
            if self.errors[0][1]:
                return "{0} ({1})".format(*self.errors[0])
            return self.errors[0][0]
        s = [
            "{0} ({1})".format(*error) if error[1] else error[0]
            for error in self.errors
        ]
        return "Multiple errors: " + "; ".join(s)

    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = http.HTTPStatus(status)
        self.msg = body.decode("utf-8", errors="replace")
        self.errors = ()
        try:
            resp_data = json.loads(self.msg)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Can't decode json from error responce '%s': %s", self.msg, exc
            )
            return

        if isinstance(resp_data, dict):
            resp_data = [resp_data]

        errors = []
        for msg in resp_data:
            if not isinstance(msg, dict) or "error" not in msg:
                logger.warning("Unexpected json in error responce: %s", self.msg)
                return
            errors.append((msg["error"], msg.get("meta", "")))

        self.errors = tuple(errors)

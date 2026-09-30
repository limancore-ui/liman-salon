class DashboardError(Exception):
    """Base dashboard application error."""


class DashboardValidationError(DashboardError):
    """Invalid dashboard request inputs."""

class SourceProviderError(Exception):
    """Base error for anything that goes wrong while acquiring a Workspace."""


class SourceAuthError(SourceProviderError):
    """Invalid, missing, or expired credentials for the requested source."""


class SourceNotFoundError(SourceProviderError):
    """The requested repository, branch, or archive could not be located/read."""


class DiagramRenderError(Exception):
    """Rendering a Mermaid script into an image failed.

    Carries a message stating the actual cause (service unreachable, script
    rejected, script too large) so the caller does not have to guess.
    """

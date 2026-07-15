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


class PandocUnavailableError(Exception):
    """Pandoc is not installed on the system.

    compiler_service raises a bare RuntimeError for this. That was fine while the
    caller caught it right around generate_docx(), but the async job runner wraps
    the whole pipeline — and a bare RuntimeError there is indistinguishable from
    a RuntimeError raised anywhere else, so an unrelated failure would be
    reported as "Pandoc missing". Naming it keeps the catch honest.
    """


class DocumentTruncatedError(Exception):
    """The model hit max_tokens before finishing the JSON document.

    Exists purely so the real cause survives. Pydantic reports truncated JSON as
    "Invalid JSON: EOF while parsing a string", which reads like the model
    emitted garbage — the next person to hit it will go hunting for a prompt bug
    that isn't there. The cause is our own output budget, so the message must say
    so. Same reasoning as ContextWindowExceededError and DiagramRenderError.
    """


class ContextWindowExceededError(Exception):
    """Contract A does not fit in the configured model's context window.

    Deliberately NOT a generic error: this is permanent for the given repo and
    model, so the caller must not tell the user to "try again". Same reasoning
    as DiagramRenderError above — carry the real cause and the real numbers
    instead of flattening them into a retry suggestion.
    """

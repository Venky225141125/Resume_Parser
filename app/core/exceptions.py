"""Typed application errors. Routes must not swallow these silently."""


class ResumeParserError(Exception):
    """Base error with a stable machine-readable code."""

    def __init__(self, message: str, *, code: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


class UnsupportedMediaError(ResumeParserError):
    def __init__(self, message: str = "Unsupported file type.") -> None:
        super().__init__(message, code="unsupported_media", http_status=415)


class FileTooLargeError(ResumeParserError):
    def __init__(self, message: str = "Uploaded file exceeds the size limit.") -> None:
        super().__init__(message, code="file_too_large", http_status=413)


class EncryptedDocumentError(ResumeParserError):
    def __init__(self, message: str = "Document is password-protected or encrypted.") -> None:
        super().__init__(message, code="encrypted_pdf", http_status=422)


class CorruptFileError(ResumeParserError):
    def __init__(self, message: str = "File is corrupt or unreadable.") -> None:
        super().__init__(message, code="corrupt_file", http_status=422)


class EmptyFileError(ResumeParserError):
    def __init__(self, message: str = "File is empty.") -> None:
        super().__init__(message, code="empty_file", http_status=422)


class ExtractionError(ResumeParserError):
    def __init__(self, message: str = "Document extraction failed.") -> None:
        super().__init__(message, code="extraction_failed", http_status=422)


class ParseTimeoutError(ResumeParserError):
    def __init__(self, message: str = "Parsing timed out.") -> None:
        super().__init__(message, code="timeout", http_status=504)


class NotImplementedStageError(ResumeParserError):
    def __init__(self, message: str = "This pipeline stage is not implemented yet.") -> None:
        super().__init__(message, code="not_implemented", http_status=501)


class UnauthorizedError(ResumeParserError):
    def __init__(self, message: str = "Invalid or missing API key.") -> None:
        super().__init__(message, code="unauthorized", http_status=401)


class NotFoundError(ResumeParserError):
    def __init__(self, message: str = "Document not found.") -> None:
        super().__init__(message, code="not_found", http_status=404)

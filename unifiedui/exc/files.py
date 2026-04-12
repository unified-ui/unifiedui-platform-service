"""Custom exceptions for file operations."""


class FileNotFoundByIdError(Exception):
    """Exception raised when a file is not found by ID."""

    def __init__(self, file_id: str):
        self.file_id = file_id
        super().__init__(f"File with ID '{file_id}' not found")


class FileTooLargeError(Exception):
    """Exception raised when a file exceeds the maximum size."""

    def __init__(self, file_size: int, max_size: int):
        self.file_size = file_size
        self.max_size = max_size
        super().__init__(f"File size {file_size} bytes exceeds maximum allowed size of {max_size} bytes")


class FileStorageNotConfiguredError(Exception):
    """Exception raised when file storage is not configured."""

    def __init__(self) -> None:
        super().__init__("File storage is not configured")

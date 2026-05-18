from __future__ import annotations


class AppError(Exception):
    pass


class ValidationError(AppError):
    pass


class NotFoundError(AppError):
    pass


class ReadOnlyModeError(AppError):
    pass


class LinuxOperationError(AppError):
    pass

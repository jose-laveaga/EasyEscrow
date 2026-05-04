from __future__ import annotations


class FileSecurityError(Exception):
    def __init__(self, *, reason_code: str, reason: str):
        super().__init__(reason)
        self.reason_code = reason_code
        self.reason = reason

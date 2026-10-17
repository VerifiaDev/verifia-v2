"""Redact provider failures while preserving request IDs and performance metrics."""
import logging


class SafeComponentLog(logging.Filter):
    def filter(self, record):
        if record.exc_info or record.name in {"verify.llm", "httpx", "httpcore", "uvicorn.access"}:
            record.msg = "backend component event (%s)"
            record.args = (record.levelname,)
            record.exc_info = record.exc_text = record.stack_info = None
        if record.name == "verify.request" and isinstance(record.args, tuple) and len(record.args) == 4:
            method, path, status, ms = record.args
            record.args = (method if method in {"GET", "POST", "OPTIONS"} else "OTHER",
                           path if path in {"/", "/health", "/health/deep", "/verify", "/verify/stream"} else "/<other>", status, ms)
        return True


class SafeOutputLog(SafeComponentLog):
    def filter(self, record):
        if not record.name.startswith("verify."):
            record.msg = "external component event (%s)"
            record.args = (record.levelname,)
            record.exc_info = record.exc_text = record.stack_info = None
        return super().filter(record)


def install_safe_logging():
    for name in ("verify.api", "verify.llm", "verify.retrieval", "verify.pipeline", "verify.stream", "verify.request", "httpx", "httpcore", "uvicorn.access"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, SafeComponentLog) for f in logger.filters):
            logger.addFilter(SafeComponentLog())
    # Descendant SDK loggers propagate directly to handlers, bypassing parent filters.
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, SafeOutputLog) for f in handler.filters):
            handler.addFilter(SafeOutputLog())

class RateLimitExceededError(Exception):
    """Minimal stub for FastAPI exception handler registration."""


# Keep alias for compatibility with slowapi's real API
RateLimitExceeded = RateLimitExceededError

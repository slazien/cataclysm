from .errors import RateLimitExceeded as RateLimitExceeded


def _rate_limit_exceeded_handler(*args, **kwargs):
    return None


class Limiter:
    def __init__(self, key_func=None):
        self.key_func = key_func
        self.enabled = True

    def limit(self, *_args, **_kwargs):
        def decorator(fn):
            return fn

        return decorator

from slowapi import Limiter
from slowapi.util import get_remote_address

# Single limiter instance shared across all routers.
# Keyed by client IP address.
limiter = Limiter(key_func=get_remote_address)

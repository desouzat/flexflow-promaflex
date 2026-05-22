import httpx

# Save the original httpx.Client.__init__ method
_original_init = httpx.Client.__init__

def _patched_init(self, *args, **kwargs):
    # Remove 'app' from kwargs if present, as newer httpx.Client versions
    # do not accept the 'app' keyword argument directly (they use transport instead,
    # which Starlette's TestClient already instantiates and passes).
    kwargs.pop('app', None)
    _original_init(self, *args, **kwargs)

# Apply the monkeypatch globally during tests
httpx.Client.__init__ = _patched_init

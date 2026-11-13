import requests

class BoundedSession(requests.Session):
    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", (5, 10))
        return super().request(method, url, **kwargs)

class BaseAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create and configure a requests session."""
        session = BoundedSession()
        session.mount(self.base_url, requests.adapters.HTTPAdapter(pool_maxsize=100))
        return session

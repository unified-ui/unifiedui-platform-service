class APIJSONBearerClient:
    def __init__(
        self,
        base_url: str,
    ):
        self._base_url = base_url

    def _url(self, endpoint: str) -> str:
        return f"{self._base_url}/{endpoint.lstrip('/')}"

    def _get_headers(self, bearer_token: str) -> dict:
        return {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}

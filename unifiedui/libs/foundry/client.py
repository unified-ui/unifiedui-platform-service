"""Microsoft Foundry API Client for conversation creation and agent discovery."""

from typing import Any

import requests

from unifiedui.logger import get_logger

logger = get_logger(__name__)


class MicrosoftFoundryError(Exception):
    """Exception raised when Microsoft Foundry API call fails."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class MicrosoftFoundryClient:
    """
    Client for Microsoft Foundry API.

    Handles conversation creation and agent discovery operations.
    """

    def __init__(self, project_endpoint: str, api_token: str, api_version: str = "2025-11-15-preview"):
        """
        Initialize the Microsoft Foundry client.

        Args:
            project_endpoint: The Foundry project endpoint
                              (e.g., https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2)
            api_token: The API token for authentication (bearer token)
            api_version: API version (default: 2025-11-15-preview)
        """
        self.project_endpoint = project_endpoint.rstrip("/")
        self.api_token = api_token
        self.api_version = api_version
        self.headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_token}"}

    def list_agents(self) -> list[dict[str, str]]:
        """List available agents from the Foundry project.

        Returns:
            List of dicts with 'id' and 'name' for each discovered agent.
        """
        url = f"{self.project_endpoint}/agents?api-version=v1"

        logger.info(
            "Listing Foundry agents",
            extra={"project_endpoint": self.project_endpoint},
        )

        try:
            logger.info("Calling Foundry API: %s", url)
            response = requests.get(url, headers=self.headers, timeout=15)
            logger.info("Foundry API response status: %s", response.status_code)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Foundry API raw response keys: %s, data count: %d",
                list(data.keys()),
                len(data.get("data", [])),
            )
            agents: list[dict[str, str]] = []
            for item in data.get("data", []):
                agent_name = item.get("name", "")
                agent_description = item.get("description", "")
                logger.info("Found agent: name=%s, description=%s", agent_name, agent_description)
                if agent_name:
                    agents.append({"id": agent_name, "name": agent_name})
            logger.info("Total agents discovered: %d", len(agents))
            return agents

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            response_body = e.response.text if e.response is not None else None
            response_headers = dict(e.response.headers) if e.response is not None else {}
            logger.warning(
                "Failed to list Foundry agents: HTTP %s — body: %s",
                status_code,
                response_body,
            )
            logger.debug(
                "Foundry agents error response headers: %s",
                {
                    k: v
                    for k, v in response_headers.items()
                    if k.lower().startswith("www-") or k.lower().startswith("x-")
                },
            )
            raise MicrosoftFoundryError(
                message=f"Failed to list Foundry agents: HTTP {status_code}",
                status_code=status_code,
                response_body=response_body,
            ) from e

        except requests.exceptions.RequestException as e:
            logger.warning("Failed to list Foundry agents: %s", e)
            raise MicrosoftFoundryError(message=f"Failed to list Foundry agents: {e!s}") from e

    def create_conversation(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Create a new conversation in Microsoft Foundry.

        Args:
            metadata: Optional metadata to attach to the conversation

        Returns:
            Response containing the conversation ID and metadata

        Raises:
            MicrosoftFoundryError: If the API call fails
        """
        url = f"{self.project_endpoint}/openai/conversations?api-version={self.api_version}"
        payload = metadata or {}

        logger.info(
            "Creating Foundry conversation",
            extra={"project_endpoint": self.project_endpoint, "api_version": self.api_version},
        )

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            conversation_id = result.get("id")

            logger.info("Foundry conversation created", extra={"conversation_id": conversation_id})

            return result

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            response_body = e.response.text if e.response is not None else None
            logger.error(
                f"Failed to create Foundry conversation: HTTP {status_code}", extra={"response_body": response_body}
            )
            raise MicrosoftFoundryError(
                message=f"Failed to create Foundry conversation: HTTP {status_code}",
                status_code=status_code,
                response_body=response_body,
            ) from e

        except requests.exceptions.RequestException as e:
            logger.error("Failed to create Foundry conversation: %s", e)
            raise MicrosoftFoundryError(message=f"Failed to create Foundry conversation: {e!s}") from e

    def get_conversation_id(self, metadata: dict[str, Any] | None = None) -> str:
        """
        Create a new conversation and return just the conversation ID.

        Args:
            metadata: Optional metadata to attach to the conversation

        Returns:
            The conversation ID string

        Raises:
            MicrosoftFoundryError: If the API call fails or response is invalid
        """
        result = self.create_conversation(metadata)
        conversation_id = result.get("id")

        if not conversation_id:
            raise MicrosoftFoundryError(message="Foundry response missing conversation ID")

        return conversation_id

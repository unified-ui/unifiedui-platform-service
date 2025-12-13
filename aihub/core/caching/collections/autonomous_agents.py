from abc import ABC, abstractmethod
from aihub.core.database.models.autonomous_agents import AutonomousAgentModel
from aihub.core.database.models.tracings import TracingModel


class BaseAutonomousAgentsCollectionCache(ABC):
    """Abstract base class for autonomous agent collection caches in the database."""

    @abstractmethod
    def get(self, agent_id: str) -> AutonomousAgentModel:
        """Retrieve an autonomous agent by its ID.

        Args:
            agent_id (str): The ID of the autonomous agent to retrieve.

        Returns:
            AutonomousAgentModel: The autonomous agent data.
        """
        pass

    @abstractmethod
    def get_list(self) -> list[AutonomousAgentModel]:
        """List all autonomous agents in the collection.

        Returns:
            list[AutonomousAgentModel]: A list of all autonomous agents.
        """
        pass

    @abstractmethod
    def get_tracings(self, agent_id: str) -> list[TracingModel]:
        """Retrieve all tracing entries for a specific autonomous agent.

        Args:
            agent_id (str): The ID of the autonomous agent.

        Returns:
            list[TracingModel]: A list of tracing entries related to the agent.
        """
        pass

    @abstractmethod
    def get_tracing(self, agent_id: str, tracing_id: str) -> TracingModel:
        """Retrieve a specific tracing entry for an autonomous agent.

        Args:
            agent_id (str): The ID of the autonomous agent.
            tracing_id (str): The ID of the tracing entry.

        Returns:
            TracingModel: The tracing entry data.
        """
        pass

    @abstractmethod
    def get_permissions(self, agent_id: str) -> dict:
        """Retrieve permissions for a specific autonomous agent.
        TODO: Define permission model.

        Args:
            agent_id (str): The ID of the autonomous agent.

        Returns:
            dict: The permissions associated with the autonomous agent.
        """
        pass

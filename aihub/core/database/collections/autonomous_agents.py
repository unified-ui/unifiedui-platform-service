from abc import ABC, abstractmethod
from aihub.core.database.models.autonomous_agents import AutonomousAgentModel
from aihub.core.database.models.tracings import TracingModel


class BaseAutonomousAgentsCollectionClient(ABC):
    """Abstract base class for autonomous agent collection clients in the database."""

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
    def create(self, agent: AutonomousAgentModel) -> AutonomousAgentModel:
        """Register a new autonomous agent in the collection.

        Args:
            agent (AutonomousAgentModel): The autonomous agent data to create.

        Returns:
            AutonomousAgentModel: The created autonomous agent.
        """
        pass

    @abstractmethod
    def update(self, agent_id: str, agent: AutonomousAgentModel) -> AutonomousAgentModel:
        """Update an existing autonomous agent in the collection (PATCH).

        Args:
            agent_id (str): The ID of the autonomous agent to update.
            agent (AutonomousAgentModel): The new autonomous agent data.

        Returns:
            AutonomousAgentModel: The updated autonomous agent.
        """
        pass

    @abstractmethod
    def delete(self, agent_id: str) -> None:
        """Delete an autonomous agent from the collection.

        Args:
            agent_id (str): The ID of the autonomous agent to delete.
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
    def create_tracing(self, agent_id: str, tracing: TracingModel) -> TracingModel:
        """Create a new tracing entry for an autonomous agent.

        Args:
            agent_id (str): The ID of the autonomous agent.
            tracing (TracingModel): The tracing data to create.

        Returns:
            TracingModel: The created tracing entry.
        """
        pass

    @abstractmethod
    def append_tracing(self, agent_id: str, tracing_id: str, tracing_data: dict) -> TracingModel:
        """Append data to an existing tracing entry.

        Args:
            agent_id (str): The ID of the autonomous agent.
            tracing_id (str): The ID of the tracing entry to append to.
            tracing_data (dict): The data to append to the tracing entry.

        Returns:
            TracingModel: The updated tracing entry.
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

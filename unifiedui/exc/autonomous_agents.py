"""Custom exception for autonomous agents."""


class AutonomousAgentNotFoundError(Exception):
    """Exception raised when an autonomous agent is not found."""

    def __init__(self, autonomous_agent_id: str):
        self.autonomous_agent_id = autonomous_agent_id
        super().__init__(f"Autonomous agent with ID '{autonomous_agent_id}' not found")


class AutonomousAgentPermissionNotFoundError(Exception):
    """Exception raised when an autonomous agent permission is not found."""

    def __init__(self, principal_id: str):
        self.principal_id = principal_id
        super().__init__(f"Permission for principal '{principal_id}' not found")


class AutonomousAgentConfigValidationError(Exception):
    """Exception raised when autonomous agent configuration validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class UnsupportedAutonomousAgentTypeError(Exception):
    """Exception raised when an unsupported autonomous agent type is used."""

    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        super().__init__(f"Unsupported autonomous agent type: {agent_type}")


class AutonomousAgentKeyNotFoundError(Exception):
    """Exception raised when an autonomous agent API key is not found."""

    def __init__(self, autonomous_agent_id: str, key_number: int):
        self.autonomous_agent_id = autonomous_agent_id
        self.key_number = key_number
        super().__init__(f"Key {key_number} not found for autonomous agent '{autonomous_agent_id}'")


class AutonomousAgentApiKeysNotAllowedError(Exception):
    """Exception raised when API key access is attempted but not allowed for this agent."""

    def __init__(self, autonomous_agent_id: str):
        self.autonomous_agent_id = autonomous_agent_id
        super().__init__(
            f"API key authentication is not allowed for autonomous agent '{autonomous_agent_id}'. Use Bearer token with a service principal instead."
        )

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

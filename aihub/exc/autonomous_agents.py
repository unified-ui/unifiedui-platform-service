"""Custom exception for autonomous agents."""


class AutonomousAgentNotFoundError(Exception):
    """Exception raised when an autonomous agent is not found."""
    
    def __init__(self, autonomous_agent_id: str):
        self.autonomous_agent_id = autonomous_agent_id
        super().__init__(f"Autonomous agent with ID '{autonomous_agent_id}' not found")

"""Custom exceptions for ReACT agents."""


class ReActAgentNotFoundError(Exception):
    """Exception raised when a ReACT agent is not found."""

    def __init__(self, re_act_agent_id: str):
        """Initialize ReActAgentNotFoundError.

        Args:
            re_act_agent_id: ID of the ReACT agent that was not found
        """
        self.re_act_agent_id = re_act_agent_id
        super().__init__(f"ReACT Agent with ID '{re_act_agent_id}' not found")

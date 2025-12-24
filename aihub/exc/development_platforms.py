"""Custom exception for development platforms."""


class DevelopmentPlatformNotFoundError(Exception):
    """Exception raised when a development platform is not found."""
    
    def __init__(self, development_platform_id: str):
        self.development_platform_id = development_platform_id
        super().__init__(f"Development platform with ID '{development_platform_id}' not found")

"""Tool configuration validators using factory pattern."""
from abc import ABC, abstractmethod
from typing import Dict, Any

from pydantic import BaseModel

from unifiedui.core.database.enums import ToolTypeEnum
from unifiedui.exc.tools import (
    ToolConfigValidationError, 
    UnsupportedToolTypeError
)
from unifiedui.logger import get_logger


logger = get_logger(__name__)


# ========== Base Validator Interface ==========

class BaseToolConfigValidator(ABC):
    """Abstract base class for tool config validators."""
    
    @abstractmethod
    def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the configuration and return the validated config.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            ToolConfigValidationError: If validation fails
        """
        pass
    
    @abstractmethod
    def get_supported_type(self) -> ToolTypeEnum:
        """Get the tool type this validator supports."""
        pass


# ========== MCP Server Validator ==========

class MCPServerConfigValidator(BaseToolConfigValidator):
    """Validator for MCP Server tool configuration."""
    
    def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate MCP Server configuration.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            ToolConfigValidationError: If validation fails
        """
        # TODO: Implement MCP Server config validation when schema is defined
        # For now, accept any config
        logger.debug("MCP Server config validation (passthrough)", extra={"config_keys": list(config.keys())})
        return config
    
    def get_supported_type(self) -> ToolTypeEnum:
        return ToolTypeEnum.MCP_SERVER


# ========== OpenAPI Definition Validator ==========

class OpenAPIDefinitionConfigValidator(BaseToolConfigValidator):
    """Validator for OpenAPI Definition tool configuration."""
    
    def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate OpenAPI Definition configuration.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            ToolConfigValidationError: If validation fails
        """
        # TODO: Implement OpenAPI Definition config validation when schema is defined
        # For now, accept any config
        logger.debug("OpenAPI Definition config validation (passthrough)", extra={"config_keys": list(config.keys())})
        return config
    
    def get_supported_type(self) -> ToolTypeEnum:
        return ToolTypeEnum.OPENAPI_DEFINITION


# ========== Factory ==========

class ToolConfigValidatorFactory:
    """Factory for creating tool config validators based on tool type."""
    
    _validators: Dict[ToolTypeEnum, BaseToolConfigValidator] = {
        ToolTypeEnum.MCP_SERVER: MCPServerConfigValidator(),
        ToolTypeEnum.OPENAPI_DEFINITION: OpenAPIDefinitionConfigValidator(),
    }
    
    @classmethod
    def get_validator(cls, tool_type: str) -> BaseToolConfigValidator:
        """
        Get the appropriate validator for the given tool type.
        
        Args:
            tool_type: Tool type string (MCP_SERVER, OPENAPI_DEFINITION)
            
        Returns:
            Appropriate validator instance
            
        Raises:
            UnsupportedToolTypeError: If tool type is not supported
        """
        try:
            enum_type = ToolTypeEnum(tool_type)
        except ValueError:
            raise UnsupportedToolTypeError(tool_type)
        
        validator = cls._validators.get(enum_type)
        if not validator:
            raise UnsupportedToolTypeError(tool_type)
        
        return validator
    
    @classmethod
    def validate_config(cls, tool_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a tool configuration using the appropriate validator.
        
        Args:
            tool_type: Tool type string
            config: Configuration dictionary to validate
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            UnsupportedToolTypeError: If tool type is not supported
            ToolConfigValidationError: If validation fails
        """
        validator = cls.get_validator(tool_type)
        return validator.validate(config)

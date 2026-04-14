class CogniWeaveException(Exception):
    """Base exception for CogniWeave."""


class ConfigException(CogniWeaveException):
    pass


class LLMException(CogniWeaveException):
    pass


class AgentException(CogniWeaveException):
    pass


class ToolException(CogniWeaveException):
    pass


class MemoryException(CogniWeaveException):
    pass

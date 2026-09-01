class CoreException(Exception):
    pass


class ServiceCallException(CoreException):
    """Service call failed"""


class NodeException(CoreException):
    """Node failed"""


class NodeExceptionRecoverable(NodeException):
    """Node failed, but retrying makes sense"""


class NodeExceptionNonRecoverable(NodeException):
    """Node failed and needs re-initialising"""


class RWSException(CoreException):
    """Robot Web Services communication failed"""

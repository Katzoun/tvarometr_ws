"""Base class for the nodes in this package.

Built on the ROS 2 managed-node lifecycle, so `ros2 lifecycle`, launch's
LifecycleNode actions and any off-the-shelf lifecycle manager work against these
nodes without knowing anything about this project. Nodes get the standard
unconfigured / inactive / active / finalized states and the standard
~/change_state and ~/get_state services for free.

What is left here is only what ROS does not already give us: one shared callback
group and a synchronous service call that does not deadlock the executor.
"""

import time

from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.client import Client
from rclpy.lifecycle import Node as LifecycleNode

from tvarometr_robot_control.constants import CALL_TIMEOUT_SEC
from tvarometr_robot_control.exceptions import NodeExceptionRecoverable, ServiceCallException


class ManagedNode(LifecycleNode):
    """Managed node with a couple of shared conveniences.

    Subclasses implement the lifecycle hooks they care about - on_configure,
    on_activate, on_deactivate, on_cleanup, on_shutdown, on_error - and return
    TransitionCallbackReturn.SUCCESS or FAILURE from them.
    """

    def __init__(self, node_name: str, **kwargs):
        super().__init__(node_name, **kwargs)
        self.NODE_NAME = node_name
        self.logger = self.get_logger()
        self.cb_group = ReentrantCallbackGroup()

    def call_service_sync(self, client: Client, request, timeout_sec=CALL_TIMEOUT_SEC):
        """Blocking service call that is safe to make from inside a callback.

        Uses call_async plus a wait loop rather than call(), which deadlocks when
        it blocks an executor thread from inside another callback. Needs a
        MultiThreadedExecutor with a spare thread to pick up the response.
        """
        future = None
        try:
            future = client.call_async(request)
            start = time.monotonic()
            while not future.done():
                if time.monotonic() - start > timeout_sec:
                    client.remove_pending_request(future)
                    raise ServiceCallException(f"Service call timed out after {timeout_sec}s")
                time.sleep(0.01)
            return future.result()
        except ServiceCallException:
            raise
        except Exception as e:
            if future is not None and not future.done():
                client.remove_pending_request(future)
            self.logger.error(f"Service call failed for {client.srv_name}: {e}")
            raise NodeExceptionRecoverable(f"Service call failed: {e}") from e

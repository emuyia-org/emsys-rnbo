# -*- coding: utf-8 -*-
"""
Service for handling OSC communication with the RNBO patch.
Sends parameter changes and potentially receives status updates.
"""

import threading
import time
from typing import Optional, Callable, Any

# Use absolute imports
from emsys.config import settings

# Import python-osc library components
try:
    from pythonosc import udp_client
    from pythonosc import dispatcher
    from pythonosc import osc_server
    # from pythonosc.osc_server import BlockingOSCUDPServer # Use non-blocking later if needed
    PYTHONOSC_AVAILABLE = True
except ImportError:
    PYTHONOSC_AVAILABLE = False
    print("Warning: python-osc library not found. OSC functionality will be disabled.")
    # Define dummy classes if library is missing to prevent runtime errors on init
    class udp_client: pass
    class dispatcher: pass
    class osc_server: pass

# Configuration constants (Add these to settings.py later)
RNBO_TARGET_IP = getattr(settings, 'RNBO_TARGET_IP', "127.0.0.1") # Default to localhost
RNBO_TARGET_PORT = getattr(settings, 'RNBO_TARGET_PORT', 9001)     # Default RNBO send port
OSC_RECEIVE_IP = getattr(settings, 'OSC_RECEIVE_IP', "127.0.0.1")   # Default to localhost
OSC_RECEIVE_PORT = getattr(settings, 'OSC_RECEIVE_PORT', 9002)   # Port for this app to listen on

class OSCService:
    """Manages OSC communication with the RNBO patch."""

    def __init__(self, status_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the OSC service.

        Args:
            status_callback: An optional function to call with status updates.
        """
        self._status_callback = status_callback if status_callback else lambda msg: print(f"OSC Status: {msg}")
        self.client: Optional[udp_client.SimpleUDPClient] = None
        self.server: Optional[osc_server.ThreadingOSCUDPServer] = None # Use Threading server
        self.dispatcher: Optional[dispatcher.Dispatcher] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running: bool = False

        if not PYTHONOSC_AVAILABLE:
            self._status_callback("OSC Disabled: python-osc library not installed.")
            return

        self._initialize_client()
        # self._initialize_server() # Initialize server later if needed

    def _initialize_client(self):
        """Initializes the OSC client."""
        try:
            self.client = udp_client.SimpleUDPClient(RNBO_TARGET_IP, RNBO_TARGET_PORT)
            self._status_callback(f"OSC Client ready to send to {RNBO_TARGET_IP}:{RNBO_TARGET_PORT}")
            print(f"OSC Client initialized for {RNBO_TARGET_IP}:{RNBO_TARGET_PORT}")
        except Exception as e:
            self.client = None
            error_msg = f"Failed to initialize OSC Client: {e}"
            self._status_callback(error_msg)
            print(error_msg)

    # --- Placeholder for Server Initialization ---
    # def _initialize_server(self):
    #     """Initializes the OSC server in a separate thread."""
    #     try:
    #         self.dispatcher = dispatcher.Dispatcher()
    #         # Add default handlers or specific handlers here if needed
    #         # self.dispatcher.map("/rnbo/feedback/*", self._handle_rnbo_feedback)
    #         self.dispatcher.set_default_handler(self._default_osc_handler)

    #         self.server = osc_server.ThreadingOSCUDPServer(
    #             (OSC_RECEIVE_IP, OSC_RECEIVE_PORT), self.dispatcher)
    #         self.server_thread = threading.Thread(target=self._run_server, daemon=True)
    #         self.is_running = True
    #         self.server_thread.start()
    #         self._status_callback(f"OSC Server listening on {OSC_RECEIVE_IP}:{OSC_RECEIVE_PORT}")
    #         print(f"OSC Server started on {OSC_RECEIVE_IP}:{OSC_RECEIVE_PORT}")
    #     except Exception as e:
    #         self.server = None
    #         self.server_thread = None
    #         self.is_running = False
    #         error_msg = f"Failed to initialize OSC Server: {e}"
    #         self._status_callback(error_msg)
    #         print(error_msg)

    # def _run_server(self):
    #     """Target function for the server thread."""
    #     if self.server:
    #         print("OSC server thread running...")
    #         self.server.serve_forever()
    #         print("OSC server thread stopped.")

    # def _default_osc_handler(self, address, *args):
    #     """Handles unmapped OSC messages."""
    #     print(f"OSC Received (Default Handler): {address} {args}")

    # --- Sending Methods ---

    def send_message(self, address: str, value: Any):
        """
        Sends an OSC message to the configured RNBO target.

        Args:
            address: The OSC address path (e.g., "/rnbo/inst/0/params/myparam").
            value: The value(s) to send. Can be a single value or a list/tuple.
        """
        if not self.client:
            # print(f"OSC Client not available. Cannot send: {address} {value}") # Can be noisy
            return

        try:
            # print(f"OSC Sending: {address} {value}") # <<< RE-COMMENTED Debug print
            self.client.send_message(address, value)
        except Exception as e:
            error_msg = f"Error sending OSC message {address} {value}: {e}"
            # self._status_callback(error_msg) # Can be noisy
            print(error_msg)

    def send_rnbo_param(self, param_name: str, value: Any, instance_index: int = 0):
        """
        Sends a specifically formatted message to control a RNBO parameter.

        Args:
            param_name: The name of the RNBO parameter (can be the full path).
            value: The value to set the parameter to.
            instance_index: The index of the RNBO instance (usually 0).
        """
        # Construct the standard RNBO parameter address
        # If param_name already starts with '/', assume it's the full path
        if param_name.startswith('/'):
            address = param_name
        else:
            # Otherwise, assume it's relative and prepend the standard prefix
            address = f"/rnbo/inst/{instance_index}/params/{param_name}"
        self.send_message(address, value)

    # --- Service Lifecycle ---

    def stop(self):
        """Stops the OSC server thread gracefully."""
        if not PYTHONOSC_AVAILABLE:
            return

        self.is_running = False
        if self.server:
            print("Shutting down OSC server...")
            self._status_callback("OSC Server shutting down...")
            try:
                self.server.shutdown() # Signal the server loop to exit
                self.server.server_close() # Close the socket
            except Exception as e:
                 print(f"Error during OSC server shutdown: {e}")
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0) # Wait for thread to finish
            if self.server_thread.is_alive():
                 print("Warning: OSC server thread did not terminate cleanly.")
        print("OSC Service stopped.")
        self._status_callback("OSC Service stopped.")

    def get_status_string(self) -> str:
        """Returns a string summarizing the current OSC connection status."""
        if not PYTHONOSC_AVAILABLE:
            return "OSC: Disabled"

        client_status = "Client: OK" if self.client else "Client: Error"
        # server_status = "Server: Running" if self.is_running and self.server else "Server: Stopped"
        server_status = "Server: N/A" # Update if server is implemented

        return f"OSC: {client_status} | {server_status}"

# Example Usage (for testing)
if __name__ == '__main__':
    print("Testing OSCService...")
    osc_service = OSCService()

    if osc_service.client:
        print("\nSending test messages...")
        # Example: Send to a hypothetical parameter
        osc_service.send_rnbo_param("volume", 0.75)
        time.sleep(0.1)
        osc_service.send_rnbo_param("filter_cutoff", 1000.0)
        time.sleep(0.1)
        # Example: Send a generic message
        osc_service.send_message("/test/message", [1, "hello", 3.14])
        print("Test messages sent.")
    else:
        print("OSC Client not initialized, cannot send messages.")

    # Keep running for a bit if server was started
    # if osc_service.is_running:
    #     print("\nOSC Server running. Press Ctrl+C to stop.")
    #     try:
    #         while True:
    #             time.sleep(1)
    #     except KeyboardInterrupt:
    #         print("\nCtrl+C received.")
    # else:
    #     print("\nOSC Server not started.")

    print("\nStopping OSCService...")
    osc_service.stop()
    print("OSCService test complete.")

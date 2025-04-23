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
    from pythonosc.osc_server import ThreadingOSCUDPServer # Use Threading server explicitly
    PYTHONOSC_AVAILABLE = True
except ImportError:
    PYTHONOSC_AVAILABLE = False
    print("Warning: python-osc library not found. OSC functionality will be disabled.")
    # Define dummy classes if library is missing to prevent runtime errors on init
    class udp_client: pass
    class dispatcher: pass
    class osc_server: pass
    class ThreadingOSCUDPServer: pass # Add dummy for Threading server

# Configuration constants
RNBO_TARGET_IP = getattr(settings, 'RNBO_TARGET_IP', "127.0.0.1") # Keep default for IP

# <<< ENSURE PORT IS READ FROM SETTINGS ONLY >>>
# Remove the default value '9001' to guarantee it uses settings.py
try:
    RNBO_TARGET_PORT = settings.RNBO_TARGET_PORT # Read directly from settings
    print(f"DEBUG: Read RNBO_TARGET_PORT from settings: {RNBO_TARGET_PORT}") # Add confirmation
except AttributeError:
    print("CRITICAL ERROR: RNBO_TARGET_PORT not found in settings.py!")
    # Assign a dummy value or raise an error to prevent client init with wrong port
    RNBO_TARGET_PORT = -1 # Or raise ConfigurationError("RNBO_TARGET_PORT missing")

OSC_RECEIVE_IP = getattr(settings, 'OSC_RECEIVE_IP', "127.0.0.1")
OSC_RECEIVE_PORT = getattr(settings, 'OSC_RECEIVE_PORT', 1235)
# <<< END PORT CONFIGURATION CHANGE >>>

class OSCService:
    """Manages OSC communication with the RNBO patch."""

    def __init__(self,
                 status_callback: Optional[Callable[[str], None]] = None,
                 rnbo_outport_callback: Optional[Callable[[str, Any], None]] = None):
        """
        Initialize the OSC service.

        Args:
            status_callback: An optional function to call with status updates.
            rnbo_outport_callback: An optional function to call when an RNBO outport message is received.
                                   It receives (address: str, value: Any).
        """
        self._status_callback = status_callback if status_callback else lambda msg: print(f"OSC Status: {msg}")
        self._rnbo_outport_callback = rnbo_outport_callback # <<< STORE CALLBACK
        self.client: Optional[udp_client.SimpleUDPClient] = None
        self.server: Optional[ThreadingOSCUDPServer] = None # Use Threading server
        self.dispatcher: Optional[dispatcher.Dispatcher] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running: bool = False

        if not PYTHONOSC_AVAILABLE:
            self._status_callback("OSC Disabled: python-osc library not installed.")
            return

        self._initialize_client()
        self._initialize_server() # <<< ENABLE SERVER INITIALIZATION

    def _initialize_client(self):
        """Initializes the OSC client and registers this app as a listener."""
        try:
            print(f"DEBUG: Initializing OSC client for {RNBO_TARGET_IP}:{RNBO_TARGET_PORT}")
            self.client = udp_client.SimpleUDPClient(RNBO_TARGET_IP, RNBO_TARGET_PORT)
            self._status_callback(f"OSC Client ready to send to {RNBO_TARGET_IP}:{RNBO_TARGET_PORT}")
            print(f"OSC Client initialized for {RNBO_TARGET_IP}:{RNBO_TARGET_PORT}")

            # <<< ADD LISTENER REGISTRATION >>>
            # After client is confirmed, tell RNBO to send outport messages back to us
            listener_address = f"{OSC_RECEIVE_IP}:{OSC_RECEIVE_PORT}"
            print(f"DEBUG: Registering OSC listener with RNBO: {listener_address}")
            # Use the generic send_message method
            self.send_message("/rnbo/listeners/add", listener_address)
            # Add a small delay to allow RNBO to process the listener add command
            time.sleep(0.1)
            print(f"DEBUG: Sent listener registration command to RNBO.")
            # <<< END LISTENER REGISTRATION >>>

        except Exception as e:
            self.client = None
            error_msg = f"Failed to initialize OSC Client ({RNBO_TARGET_IP}:{RNBO_TARGET_PORT}): {e}"
            self._status_callback(error_msg)
            print(error_msg)

    # --- Server Initialization ---
    def _initialize_server(self):
        """Initializes the OSC server."""
        if not PYTHONOSC_AVAILABLE:
            self._status_callback("OSC Server disabled (python-osc not found)")
            return

        self.dispatcher = dispatcher.Dispatcher()

        # --- Map RNBO Outports ---
        # Use the correct path format: /rnbo/inst/0/messages/out/<outport_name>
        print("Mapping OSC outports:") # Add log

        outports_to_map = [
            "Transport.Status",
            "Transport.4nCount",
            "Transport.LoadNowBeat",
            "Transport.TransportTempo",
            "Transport.TempoRamp",
            "Set.PGM1",
            "Set.PGM2",
            "Tin.Toggle"
            # Add any other outports you need to listen to here
        ]

        for outport_name in outports_to_map:
            # <<< CORRECTED PATH with /messages >>>
            osc_address = f"/rnbo/inst/0/messages/out/{outport_name}"
            self.dispatcher.map(osc_address, self._handle_rnbo_outport)
            print(f"  - Mapped {osc_address}") # Add log

        # Map a default handler for unmapped messages (optional, for debugging)
        # self.dispatcher.set_default_handler(self._default_osc_handler)

        try:
            # Use ThreadingOSCUDPServer for background operation
            print(f"DEBUG: Attempting to bind OSC Server to {OSC_RECEIVE_IP}:{OSC_RECEIVE_PORT}")
            self.server = ThreadingOSCUDPServer(
                (OSC_RECEIVE_IP, OSC_RECEIVE_PORT), self.dispatcher)

            # <<< SET is_running = True BEFORE starting thread >>>
            self.is_running = True # Assume success unless exception occurs

            self.server_thread = threading.Thread(target=self._run_server) # Use _run_server
            self.server_thread.daemon = True
            self.server_thread.start()
            self._status_callback(f"OSC Server listening on {OSC_RECEIVE_IP}:{OSC_RECEIVE_PORT}")
            print(f"OSC Server started on {OSC_RECEIVE_IP}:{OSC_RECEIVE_PORT}")
        except Exception as e:
            # <<< SET is_running = False on failure >>>
            self.is_running = False
            self.server = None
            self.server_thread = None
            error_msg = f"Failed to initialize OSC Server ({OSC_RECEIVE_IP}:{OSC_RECEIVE_PORT}): {e}"
            self._status_callback(error_msg)
            print(error_msg)

    def _run_server(self):
        """Target function for the server thread."""
        if self.server:
            # <<< REMOVE is_running = True from here >>>
            # self.is_running = True # Now set in _initialize_server
            print("OSC server thread running...")
            try:
                self.server.serve_forever()
            except Exception as e:
                if self.is_running:
                    print(f"Error in OSC server loop: {e}")
                    self._status_callback(f"OSC Server Error: {e}")
            finally:
                print("OSC server thread stopped.")
                self.is_running = False # Set to false when loop actually exits
        else: # <<< ADDED ELSE >>>
             print("ERROR: _run_server called but self.server is None")
             self.is_running = False # Ensure flag is false if server wasn't created

    def _default_osc_handler(self, address, *args):
        """Handles unmapped OSC messages."""
        # Reduce noise by only printing if not a known outport path structure
        if not address.startswith("/rnbo/inst/0/out/"):
            print(f"OSC Received (Default Handler): {address} {args}")

    def _handle_rnbo_outport(self, address: str, *args: Any):
        """
        Generic handler for mapped RNBO outports.
        Calls the registered callback function.
        """
        # print(f"OSC Received: {address} {args}") # Debug: Can be very noisy
        if self._rnbo_outport_callback:
            # Extract the single value if args contains only one item
            value = args[0] if len(args) == 1 else args
            # Extract the outport name from the address
            outport_name = address.split('/')[-1]
            try:
                # Call the App's handler
                self._rnbo_outport_callback(outport_name, value)
            except Exception as e:
                print(f"Error in rnbo_outport_callback for {outport_name}: {e}")
                import traceback
                traceback.print_exc()

    # --- Sending Methods ---

    def send_rnbo_param(self, param_path: str, value: Any):
        """
        Sends a value to a specific RNBO parameter via OSC.

        Args:
            param_path (str): The RNBO parameter path (e.g., "p_obj-6/tempo/Transport.Tempo").
            value: The value to send (int, float, or str).
        """
        if not self.client:
            print(f"DEBUG OSC Send Aborted: Client is None for {param_path}")
            return

        # <<< DETAILED DEBUGGING - Check for _address and _port >>>
        print(f"DEBUG OSC Send Check: About to access attributes for {param_path}")
        print(f"DEBUG OSC Send Check: self.client is type: {type(self.client)}")
        try:
            # Explicitly check for attributes right before use
            has_address = hasattr(self.client, '_address') # <<< CHECK FOR _address >>>
            has_port = hasattr(self.client, '_port')
            print(f"DEBUG OSC Send Check: hasattr _address: {has_address}, hasattr _port: {has_port}") # <<< UPDATED PRINT >>>

            # If attributes are missing, print more info and avoid the error
            if not has_address or not has_port: # <<< CHECK has_address >>>
                print(f"ERROR: self.client ({type(self.client)}) is missing expected attributes (_address/_port)!") # <<< UPDATED PRINT >>>
                try:
                    print(f"DEBUG OSC Send Check: dir(self.client) = {dir(self.client)}")
                except: pass
                return # Avoid the AttributeError

        except Exception as check_err:
            print(f"DEBUG OSC Send Check: Error during attribute check: {check_err}")
            return
        # <<< END DETAILED DEBUGGING >>>

        full_address = f"/rnbo/inst/0/params/{param_path.strip('/')}"

        try:
            # <<< USE _address and _port >>>
            target_ip = self.client._address
            target_port = self.client._port
            print(f"DEBUG OSC Send: Target={target_ip}:{target_port}, Address='{full_address}', Value='{value}' (Type: {type(value)})")

            self.send_message(full_address, value)
            # self._status_callback(f"Sent OSC: {full_address} = {value}") # Can be noisy
        except AttributeError as ae:
             # Catch the specific error again just in case, and provide context
             print(f"ERROR: Still got AttributeError accessing _address/_port for {param_path} despite checks: {ae}") # <<< UPDATED PRINT >>>
             print(f"ERROR Context: self.client type was {type(self.client)}")
        except Exception as e:
            error_msg = f"Error sending OSC parameter {full_address}: {e}"
            print(error_msg)
            self._status_callback(error_msg)

    def send_message(self, address: str, value: Any):
        """Sends a generic OSC message."""
        if not self.client:
            # print("OSC Client not initialized. Cannot send message.") # Reduce noise
            return
        try:
            self.client.send_message(address, value)
            # print(f"OSC Sent: {address} {value}") # Can be very noisy
        except Exception as e:
            error_msg = f"Error sending OSC message {address}: {e}"
            print(error_msg)
            self._status_callback(error_msg)
            # Consider if re-initialization is needed on certain errors

    # --- Service Lifecycle ---

    def stop(self):
        """Stops the OSC server thread gracefully."""
        if not PYTHONOSC_AVAILABLE:
            return

        # Signal the server thread to stop *before* shutting down the server
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
            # Wait for the thread to finish after shutdown() is called
            self.server_thread.join(timeout=2.0) # Increased timeout
            if self.server_thread.is_alive():
                 print("Warning: OSC server thread did not terminate cleanly.")
        print("OSC Service stopped.")
        self._status_callback("OSC Service stopped.")

    def get_status_string(self) -> str:
        """Returns a string summarizing the current OSC connection status."""
        if not PYTHONOSC_AVAILABLE:
            return "OSC: Disabled"

        client_status = "Client: OK" if self.client else "Client: Error"
        # Check self.server as well for a more accurate status
        server_status = "Server: Running" if self.is_running and self.server else "Server: Stopped"
        if PYTHONOSC_AVAILABLE and not self.server and not self.is_running and self.dispatcher: # Check dispatcher to see if init was attempted
             server_status = "Server: Error" # More specific error state

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

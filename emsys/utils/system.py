import subprocess
import os
import logging

# Configure logging (or use print)
logger = logging.getLogger(__name__)

RNBO_SERVICE_NAME = "rnbooscquery-emsys.service"

def start_rnbo_service_if_needed():
    """
    Attempts to start the RNBO systemd service if the script is run directly
    (not under systemd) and the service isn't already active.
    Uses --job-mode=ignore-dependencies to avoid starting emsys-python.service again.
    Requires passwordless sudo for 'systemctl start rnbooscquery-emsys.service'.
    """
    # Check if running under systemd (INVOCATION_ID is usually set by systemd)
    if os.getenv('INVOCATION_ID'):
        logger.info("Running under systemd, skipping manual start of %s.", RNBO_SERVICE_NAME)
        return False

    # Check if the service is already active/running (system service)
    try:
        status_command = ['systemctl', 'is-active', RNBO_SERVICE_NAME]
        result = subprocess.run(status_command, capture_output=True, text=True, check=False, timeout=5)
        service_status = result.stdout.strip()
        if service_status == 'active':
             logger.info("%s is already active, no need to start.", RNBO_SERVICE_NAME)
             return True # Already running
        elif service_status == 'activating':
             logger.info("%s is currently activating, no need to start.", RNBO_SERVICE_NAME)
             return True # Already starting

    except FileNotFoundError:
         logger.warning("'systemctl' command not found, cannot check service status. Will attempt start.")
    except subprocess.TimeoutExpired:
         logger.warning("Timeout checking status for %s. Will attempt start.", RNBO_SERVICE_NAME)
    except Exception as e:
         logger.warning("Could not check status for %s: %s. Will attempt start.", RNBO_SERVICE_NAME, e)

    # Proceed to attempt starting the service IGNORING DEPENDENCIES
    # Use --job-mode=ignore-dependencies <<< CORRECTED FLAG HERE
    start_command = ['sudo', 'systemctl', 'start', '--job-mode=ignore-dependencies', RNBO_SERVICE_NAME]
    logger.info("Attempting to start RNBO service (ignoring dependencies): %s", ' '.join(start_command))
    try:
        result = subprocess.run(start_command, check=False, capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            logger.info("Successfully issued start command for %s (or it was already running/activating).", RNBO_SERVICE_NAME)
            return True
        else:
            logger.error("Failed to start %s (exit code %d).", RNBO_SERVICE_NAME, result.returncode)
            if result.stderr:
                logger.error("Stderr: %s", result.stderr.strip())
            if result.stdout:
                 logger.info("Stdout: %s", result.stdout.strip())
            logger.error("Ensure passwordless sudo is configured for 'systemctl start %s'.", RNBO_SERVICE_NAME)
            return False

    except FileNotFoundError:
        logger.error("Error: 'sudo' command not found. Cannot start %s.", RNBO_SERVICE_NAME)
    except subprocess.TimeoutExpired:
         logger.error("Timeout waiting for 'systemctl start %s' command.", RNBO_SERVICE_NAME)
    except Exception as e:
        logger.error("An unexpected error occurred while starting %s: %s", RNBO_SERVICE_NAME, e)

    return False

# Example of how to use logging if not configured globally
# if __name__ == '__main__':
#    logging.basicConfig(level=logging.INFO)
#    logger.info("Testing RNBO service start...")
#    start_rnbo_service_if_needed()
#    logger.info("Test complete.")
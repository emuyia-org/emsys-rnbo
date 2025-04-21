import subprocess
import os
import logging
import time

# Configure logging (or use print)
logger = logging.getLogger(__name__)

RNBO_SERVICE_NAME = "rnbooscquery-emsys.service"
MANUAL_START_DELAY_S = 1.0 # Keep the delay

# Consider renaming the function if "if_needed" is no longer accurate,
# but we'll keep it for now to minimize changes elsewhere.
def start_rnbo_service_if_needed():
    """
    Attempts to ensure the RNBO systemd service is started.
    Includes a short delay before issuing the start command if needed.
    Uses --job-mode=ignore-dependencies to avoid potential dependency loops.
    Requires passwordless sudo for 'systemctl start rnbooscquery-emsys.service'.
    """
    logger.info("Ensuring %s service is started...", RNBO_SERVICE_NAME) # Changed log message

    # Check if the service is already active/running (system service)
    try:
        status_command = ['systemctl', 'is-active', RNBO_SERVICE_NAME]
        result = subprocess.run(status_command, capture_output=True, text=True, check=False, timeout=5)
        service_status = result.stdout.strip()
        if service_status == 'active':
             logger.info("%s is already active, no need to issue start command.", RNBO_SERVICE_NAME)
             return True # Already running
        elif service_status == 'activating':
             logger.info("%s is currently activating, no need to issue start command.", RNBO_SERVICE_NAME)
             return True # Already starting
        # If inactive, failed, or unknown status, proceed to start attempt below
        else:
             logger.info("%s status is '%s'. Proceeding with start attempt.", RNBO_SERVICE_NAME, service_status)

    except FileNotFoundError:
         logger.warning("'systemctl' command not found, cannot check service status. Will attempt start.")
    except subprocess.TimeoutExpired:
         logger.warning("Timeout checking status for %s. Will attempt start.", RNBO_SERVICE_NAME)
    except Exception as e:
         logger.warning("Could not check status for %s: %s. Will attempt start.", RNBO_SERVICE_NAME, e)

    # <<< Keep Delay >>>
    # This delay might still be useful even under systemd, giving a moment
    # for other things potentially happening during startup.
    logger.info("Waiting %.1f seconds before issuing start command for %s...", MANUAL_START_DELAY_S, RNBO_SERVICE_NAME)
    time.sleep(MANUAL_START_DELAY_S)
    # <<< END Delay >>>

    # Proceed to attempt starting the service IGNORING DEPENDENCIES
    # Using --job-mode=ignore-dependencies is important here to prevent
    # systemd from potentially trying to restart this python service if
    # rnbooscquery-emsys.service has Requires=emsys-python.service.
    start_command = ['sudo', 'systemctl', 'start', '--job-mode=ignore-dependencies', RNBO_SERVICE_NAME]
    logger.info("Attempting to start RNBO service (ignoring dependencies): %s", ' '.join(start_command))
    try:
        # Use check=False and evaluate returncode
        result = subprocess.run(start_command, check=False, capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            logger.info("Successfully issued start command for %s (or it was already running/activating).", RNBO_SERVICE_NAME)
            # Verify status after issuing start command (optional but good practice)
            time.sleep(0.5) # Give service a moment to potentially activate
            try:
                status_check_after = subprocess.run(['systemctl', 'is-active', RNBO_SERVICE_NAME], capture_output=True, text=True, check=False, timeout=3)
                logger.info("Status check after start attempt for %s: %s", RNBO_SERVICE_NAME, status_check_after.stdout.strip())
            except Exception:
                logger.warning("Could not verify status after start attempt.")
            return True
        else:
            # Log the error details
            logger.error("Failed to start %s (exit code %d).", RNBO_SERVICE_NAME, result.returncode)
            if result.stderr:
                logger.error("Stderr: %s", result.stderr.strip())
            if result.stdout:
                 logger.info("Stdout: %s", result.stdout.strip()) # Log stdout too, might contain info
            logger.error("Ensure passwordless sudo is configured for 'systemctl start %s'.", RNBO_SERVICE_NAME)
            return False

    except FileNotFoundError:
        logger.error("Error: 'sudo' or 'systemctl' command not found. Cannot start %s.", RNBO_SERVICE_NAME)
        return False # Indicate failure
    except subprocess.TimeoutExpired:
         logger.error("Timeout waiting for 'systemctl start %s' command.", RNBO_SERVICE_NAME)
         return False # Indicate failure
    except Exception as e:
        logger.error("An unexpected error occurred while starting %s: %s", RNBO_SERVICE_NAME, e)
        return False # Indicate failure

def stop_rnbo_service():
    """
    Attempts to stop the RNBO systemd service.
    Logs whether running under systemd or manually.
    Requires passwordless sudo for 'systemctl stop rnbooscquery-emsys.service'.
    """
    context = "manually"
    if os.getenv('INVOCATION_ID'):
        context = "under systemd"
        logger.info("Stop request initiated while running %s.", context)
    else:
        logger.info("Stop request initiated while running %s.", context)

    # Check if the service is inactive/failed first
    try:
        status_command = ['systemctl', 'is-active', RNBO_SERVICE_NAME]
        result = subprocess.run(status_command, capture_output=True, text=True, check=False, timeout=5)
        service_status = result.stdout.strip()
        if service_status in ['inactive', 'failed']:
             logger.info("%s is already inactive or failed, no need to stop.", RNBO_SERVICE_NAME)
             return True # Already stopped or failed

    except FileNotFoundError:
         logger.warning("'systemctl' command not found, cannot check service status. Will attempt stop.")
    except subprocess.TimeoutExpired:
         logger.warning("Timeout checking status for %s. Will attempt stop.", RNBO_SERVICE_NAME)
    except Exception as e:
         logger.warning("Could not check status for %s: %s. Will attempt stop.", RNBO_SERVICE_NAME, e)


    # Proceed to attempt stopping the service
    stop_command = ['sudo', 'systemctl', 'stop', RNBO_SERVICE_NAME]
    logger.info("Attempting to stop RNBO service: %s", ' '.join(stop_command))
    try:
        result = subprocess.run(stop_command, check=False, capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            logger.info("Successfully issued stop command for %s (or it was already stopped).", RNBO_SERVICE_NAME)
            return True
        else:
            # Log error, but don't necessarily treat as fatal for cleanup
            logger.error("Failed to stop %s (exit code %d).", RNBO_SERVICE_NAME, result.returncode)
            if result.stderr:
                logger.error("Stderr: %s", result.stderr.strip())
            if result.stdout:
                 logger.info("Stdout: %s", result.stdout.strip())
            logger.error("Ensure passwordless sudo is configured for 'systemctl stop %s'.", RNBO_SERVICE_NAME)
            return False

    except FileNotFoundError:
        logger.error("Error: 'sudo' command not found. Cannot stop %s.", RNBO_SERVICE_NAME)
    except subprocess.TimeoutExpired:
         logger.error("Timeout waiting for 'systemctl stop %s' command.", RNBO_SERVICE_NAME)
    except Exception as e:
        logger.error("An unexpected error occurred while stopping %s: %s", RNBO_SERVICE_NAME, e)

    return False

# Example of how to use logging if not configured globally
# if __name__ == '__main__':
#    logging.basicConfig(level=logging.INFO)
#    logger.info("Testing RNBO service start...")
#    start_rnbo_service_if_needed()
#    time.sleep(5) # Keep it running for a bit
#    logger.info("Testing RNBO service stop...")
#    stop_rnbo_service()
#    logger.info("Test complete.")
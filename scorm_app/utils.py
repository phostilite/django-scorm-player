import os
import json
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

def get_log_file_path(user_id, attempt_id):
    """Generate the path for a log file based on user_id and attempt_id."""
    return os.path.join(settings.SCORM_LOGS_DIR, str(user_id), str(attempt_id), 'progress.json')

def ensure_log_file_exists(user_id, attempt_id):
    """Ensure that the log file exists, creating it if necessary."""
    log_file_path = get_log_file_path(user_id, attempt_id)
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    if not os.path.exists(log_file_path):
        with open(log_file_path, 'w') as f:
            json.dump([], f)
    return log_file_path

def append_to_log(user_id, attempt_id, data):
    """Append a new log entry to the JSON log file with enhanced error handling."""
    log_file_path = ensure_log_file_exists(user_id, attempt_id)
    try:
        with open(log_file_path, 'r+') as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Corrupted JSON in {log_file_path}. Resetting file.")
                log_data = []
            
            new_entry = {
                'timestamp': timezone.now().isoformat(),
                'data': data
            }
            log_data.append(new_entry)
            
            f.seek(0)
            json.dump(log_data, f, indent=2)
            f.truncate()
    except Exception as e:
        logger.error(f"Error appending to log file {log_file_path}: {str(e)}")

def read_log(user_id, attempt_id):
    """Read the entire log file for a given user and attempt with error handling."""
    log_file_path = get_log_file_path(user_id, attempt_id)
    try:
        with open(log_file_path, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Corrupted JSON in {log_file_path}. Returning empty list.")
                return []
    except FileNotFoundError:
        logger.warning(f"Log file not found: {log_file_path}")
        return []
    except Exception as e:
        logger.error(f"Error reading log file {log_file_path}: {str(e)}")
        return []
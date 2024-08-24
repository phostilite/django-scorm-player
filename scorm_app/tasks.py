# tasks.py
from celery import shared_task
import zipfile
import os
import re
import json
import shutil
import pytz
from datetime import datetime
import logging
import xml.etree.ElementTree as ET
from .models import ScormPackage, SCORMStandard, TaskResult
from django.utils import timezone
from django.conf import settings
from .models import SCORMAttempt, SCORMElement

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_scorm_package(self, package_id, task_id):
    package = ScormPackage.objects.get(id=package_id)
    package.status = 'processing'
    package.save()

    task_result = TaskResult.objects.get(task_id=task_id)
    try:
        with zipfile.ZipFile(package.file.path, 'r') as zip_ref:
            extract_path = f'media/scorm_extracted/{package.id}/'
            zip_ref.extractall(extract_path)

        # Find imsmanifest.xml and parse it
        manifest_path = find_manifest(extract_path)
        logger.info(f"Manifest path: {manifest_path}")
        if not manifest_path:
            raise Exception("imsmanifest.xml not found")

        # Parse manifest and update package info
        scorm_version, launch_path = parse_manifest(manifest_path)
        package.manifest_path = os.path.relpath(manifest_path, extract_path)
        package.launch_path = launch_path

        # Insert the new code here
        # Try to find an index file, but don't require it
        index_files = ['index_lms.html', 'index.html', launch_path]
        index_path = next((os.path.join(extract_path, f) for f in index_files if os.path.exists(os.path.join(extract_path, f))), None)

        logger.info(f"Index path: {index_path}")
        if index_path and os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
                version_match = re.search(r'version: ([\d\.]+)', content)
                logger.info(f"Version match: {version_match}")
                if version_match:
                    package.version = version_match.group(1)
        else:
            logger.warning("No suitable index file found. Using version from manifest.")
            package.version = scorm_version  # Fall back to the version from the manifest

        # Set SCORM standard
        scorm_standard = get_scorm_standard(scorm_version)
        if scorm_standard:
            package.scorm_standard = scorm_standard

        package.status = 'ready'
        package.save()
        
        task_result.status = 'SUCCESS'
        task_result.result = {'package_id': package.id}
        task_result.date_done = timezone.now()
        task_result.save()
        
        return package.id
    except Exception as e:
        task_result.status = 'FAILURE'
        task_result.result = {'error': str(e)}
        task_result.date_done = timezone.now()
        task_result.save()
        package.status = 'error'
        package.save()
        raise

def find_manifest(path):
    for root, dirs, files in os.walk(path):
        if 'imsmanifest.xml' in files:
            logger.info("Found imsmanifest.xml")
            return os.path.join(root, 'imsmanifest.xml')
        elif 'tincan.xml' in files:
            logger.info("Found tincan.xml (xAPI package)")
            return os.path.join(root, 'tincan.xml')
    logger.warning("No manifest file found")
    return None

def parse_manifest(manifest_path):
    logger.info(f"Parsing manifest: {manifest_path}")
    tree = ET.parse(manifest_path)
    logger.info(f"Manifest parsed: {manifest_path}")
    root = tree.getroot()
    logger.info(f"Root element: {root}")

    # Define namespaces
    namespaces = {
        'imscp': 'http://www.imsproject.org/xsd/imscp_rootv1p1p2',
        'adlcp': 'http://www.adlnet.org/xsd/adlcp_rootv1p2',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    # Find the schemaversion
    logger.info("Finding schema version in manifest")
    schema_version = root.find('.//imscp:schemaversion', namespaces)
    logger.info(f"Schema version element: {schema_version}")
    scorm_version = schema_version.text if schema_version is not None else None
    logger.info(f"Found schema version in manifest: {scorm_version}")

    # Find the organization element
    organization = root.find('.//imscp:organizations/imscp:organization', namespaces)
    
    if organization is None:
        logger.warning("Organization element not found in manifest")
        raise ValueError("No organization found in manifest")

    # Find the first item in the organization
    item = organization.find('.//imscp:item', namespaces)
    
    if item is None:
        raise ValueError("No item found in organization")

    # Get the identifierref attribute
    identifierref = item.get('identifierref')

    if identifierref is None:
        raise ValueError("No identifierref found in item")

    # Find the resource with matching identifier
    resource = root.find(f'.//imscp:resources/imscp:resource[@identifier="{identifierref}"]', namespaces)
    
    if resource is None:
        raise ValueError(f"No resource found with identifier {identifierref}")

    # Get the href attribute
    href = resource.get('href')

    if href is None:
        raise ValueError("No href found in resource")

    # Construct the full path
    launch_path = os.path.join(os.path.dirname(manifest_path), href)

    return scorm_version, launch_path

def get_scorm_standard(version):
    logger.info(f"Determining SCORM standard for version: {version}")
    if version is None:
        logger.warning("SCORM version is None, unable to determine standard")
        return None
    if version == '1.2':
        standard, _ = SCORMStandard.objects.get_or_create(name='SCORM 1.2', version='1.2')
    elif version == '2004':
        standard, _ = SCORMStandard.objects.get_or_create(name='SCORM 2004', version='4th Edition')
    else:
        logger.warning(f"Unknown SCORM version: {version}")
        standard = None
    return standard


@shared_task
def process_scorm_logs():
    logger.info("Starting SCORM log processing task")
    log_dir = settings.SCORM_LOGS_DIR
    archive_dir = os.path.join(settings.SCORM_LOGS_DIR, 'archive')
    os.makedirs(archive_dir, exist_ok=True)
    
    processed_count = 0
    skipped_count = 0
    error_count = 0

    for user_dir in os.listdir(log_dir):
        user_path = os.path.join(log_dir, user_dir)
        if os.path.isdir(user_path):
            for attempt_dir in os.listdir(user_path):
                attempt_path = os.path.join(user_path, attempt_dir)
                if os.path.isdir(attempt_path):
                    log_file = os.path.join(attempt_path, 'progress.json')
                    if os.path.exists(log_file):
                        try:
                            if should_process_file(log_file, user_dir, attempt_dir):
                                process_log_file(log_file, user_dir, attempt_dir)
                                processed_count += 1
                                archive_log_file(log_file, archive_dir, user_dir, attempt_dir)
                            else:
                                skipped_count += 1
                        except Exception as e:
                            logger.error(f"Error processing log file {log_file}: {str(e)}")
                            error_count += 1

    logger.info(f"SCORM log processing completed. Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}")

def should_process_file(log_file, user_id, attempt_id):
    try:
        attempt = SCORMAttempt.objects.get(id=attempt_id, user_id=user_id)
        if attempt.is_complete:
            logger.info(f"Skipping completed attempt: user_id={user_id}, attempt_id={attempt_id}")
            return False
        
        file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file), tz=pytz.UTC)
        if attempt.last_processed and file_mtime <= attempt.last_processed:
            logger.info(f"Skipping unmodified log: user_id={user_id}, attempt_id={attempt_id}")
            return False
        
        return True
    except SCORMAttempt.DoesNotExist:
        logger.warning(f"SCORMAttempt not found: user_id={user_id}, attempt_id={attempt_id}")
        return True


def process_log_file(log_file, user_id, attempt_id):
    logger.info(f"Processing log file: {log_file}")
    try:
        with open(log_file, 'r') as f:
            log_data = json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in log file: {log_file}")
        return
    except Exception as e:
        logger.error(f"Error reading log file {log_file}: {str(e)}")
        return

    try:
        attempt = SCORMAttempt.objects.get(id=attempt_id, user_id=user_id)
    except SCORMAttempt.DoesNotExist:
        logger.error(f"SCORMAttempt not found for user_id: {user_id}, attempt_id: {attempt_id}")
        return

    # Process and aggregate data
    latest_status = None
    latest_score = None
    elements_updated = 0

    for entry in log_data:
        element_id = entry['data']['element_id']
        value = entry['data']['value']
        
        if element_id == 'cmi.core.lesson_status':
            latest_status = value
        elif element_id == 'cmi.core.score.raw':
            try:
                latest_score = float(value)
            except ValueError:
                logger.warning(f"Invalid score value in log file {log_file}: {value}")

        # Update or create SCORMElement
        try:
            SCORMElement.objects.update_or_create(
                scorm_attempt=attempt,
                element_id=element_id,
                defaults={'value': value}
            )
            elements_updated += 1
        except Exception as e:
            logger.error(f"Error updating SCORMElement for {element_id}: {str(e)}")

    # Update SCORMAttempt
    try:
        if latest_status:
            attempt.completion_status = latest_status
            if latest_status in ['completed', 'passed']:
                attempt.is_complete = True
        if latest_score is not None:
            attempt.score = latest_score
        attempt.last_processed = timezone.now()
        attempt.save()
        logger.info(f"Updated SCORMAttempt id: {attempt_id}, status: {latest_status}, score: {latest_score}")
    except Exception as e:
        logger.error(f"Error updating SCORMAttempt id: {attempt_id}: {str(e)}")

    logger.info(f"Processed log file {log_file}. Updated {elements_updated} elements.")

    # Optionally, delete the processed log file
    # os.remove(log_file)
    # logger.info(f"Deleted processed log file: {log_file}")

def archive_log_file(log_file, archive_dir, user_id, attempt_id):
    archive_user_dir = os.path.join(archive_dir, user_id)
    archive_attempt_dir = os.path.join(archive_user_dir, attempt_id)
    os.makedirs(archive_attempt_dir, exist_ok=True)
    archive_file = os.path.join(archive_attempt_dir, 'progress.json')
    shutil.move(log_file, archive_file)
    logger.info(f"Archived log file: {log_file} to {archive_file}")
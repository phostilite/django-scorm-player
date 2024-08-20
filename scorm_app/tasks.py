# tasks.py
from celery import shared_task
import zipfile
import os
import re
import logging
import xml.etree.ElementTree as ET
from .models import ScormPackage, SCORMStandard, TaskResult
from django.utils import timezone

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
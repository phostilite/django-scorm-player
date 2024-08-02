# tasks.py
from celery import shared_task
import zipfile
import os
import xml.etree.ElementTree as ET
from .models import ScormPackage

@shared_task
def process_scorm_package(package_id):
    package = ScormPackage.objects.get(id=package_id)
    package.status = 'processing'
    package.save()

    try:
        with zipfile.ZipFile(package.file.path, 'r') as zip_ref:
            extract_path = f'media/scorm_extracted/{package.id}/'
            zip_ref.extractall(extract_path)

        # Find imsmanifest.xml and parse it
        manifest_path = find_manifest(extract_path)
        if not manifest_path:
            raise Exception("imsmanifest.xml not found")

        # Parse manifest and update package info
        launch_path = parse_manifest(manifest_path)
        package.manifest_path = os.path.relpath(manifest_path, extract_path)
        package.launch_path = launch_path
        package.status = 'ready'
    except Exception as e:
        package.status = 'error'
        # Log the error

    package.save()

def find_manifest(path):
    for root, dirs, files in os.walk(path):
        if 'imsmanifest.xml' in files:
            return os.path.join(root, 'imsmanifest.xml')
    return None

def parse_manifest(manifest_path):
    tree = ET.parse(manifest_path)
    root = tree.getroot()

    # Define namespaces
    namespaces = {
        'adlcp': 'http://www.adlnet.org/xsd/adlcp_rootv1p2',
        'imscp': 'http://www.imsproject.org/xsd/imscp_rootv1p1p2',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    # Find the organization element
    organization = root.find('.//imscp:organizations/imscp:organization', namespaces)
    
    if organization is None:
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

    return launch_path

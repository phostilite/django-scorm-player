from django.db import models
import os
import logging

logger = logging.getLogger(__name__)

class ScormPackage(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='scorm_packages/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        absolute_url = f'/media/{self.file}'
        logger.debug(f"Generated absolute URL: {absolute_url}")
        return absolute_url

    def get_launch_url(self):
        file_name = os.path.splitext(os.path.basename(self.file.name))[0]
        base_dir = os.path.join('media', 'scorm_packages', file_name.replace(' ', '_'))
        logger.debug(f"Base directory for SCORM package: {base_dir}")
        for root, dirs, files in os.walk(base_dir):
            logger.debug(f"Walking through directory: {root}")
            for file in files:
                logger.debug(f"Checking file: {file}")
                if file.lower() == 'imsmanifest.xml':
                    relative_path = os.path.relpath(root, base_dir)
                    launch_url = f'/media/scorm_packages/{file_name.replace(" ", "_")}/{relative_path}/index_lms.html'
                    logger.debug(f"Found imsmanifest.xml, launch URL: {launch_url}")
                    return launch_url
        logger.error("imsmanifest.xml not found in SCORM package")
        return None
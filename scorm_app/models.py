from django.db import models
import os

class ScormPackage(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='scorm_packages/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f'/media/{self.file}'

    def get_launch_url(self):
        file_name = os.path.splitext(os.path.basename(self.file.name))[0]
        base_dir = os.path.join('media', 'scorm_packages', file_name.replace(' ', '_'))
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file.lower() == 'imsmanifest.xml':
                    relative_path = os.path.relpath(root, base_dir)
                    return f'/media/scorm_packages/{file_name.replace(" ", "_")}/{relative_path}/index_lms.html'
        return None
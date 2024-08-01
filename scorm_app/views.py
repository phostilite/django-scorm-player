from django.shortcuts import render, redirect
from django.views import View
from django.http import FileResponse, Http404
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from .models import ScormPackage
import zipfile
import os
from django.conf import settings

import logging

logger = logging.getLogger(__name__)

class UploadScormPackage(View):
    def get(self, request):
        logger.debug("GET request received for UploadScormPackage")
        scorm_packages = ScormPackage.objects.all()
        logger.debug(f"Retrieved {len(scorm_packages)} SCORM packages")
        return render(request, 'scorm_app/upload.html', {'scorm_packages': scorm_packages})

    def post(self, request):
        logger.debug("POST request received for UploadScormPackage")
        if 'file' in request.FILES:
            file = request.FILES['file']
            logger.debug(f"File received: {file.name}")
            title = os.path.splitext(file.name)[0]
            safe_title = title.replace(' ', '_')
            logger.debug(f"Title: {title}, Safe Title: {safe_title}")
            scorm_package = ScormPackage.objects.create(title=title, file=file)
            logger.info(f'SCORM package created: {scorm_package.pk}, title: {scorm_package.title}')
            
            # Extract the SCORM package
            zip_path = os.path.join(settings.MEDIA_ROOT, scorm_package.file.name)
            extract_path = os.path.join(settings.MEDIA_ROOT, 'scorm_packages', safe_title)
            logger.debug(f"Zip path: {zip_path}, Extract path: {extract_path}")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                logger.debug("SCORM package extracted successfully")
            except zipfile.BadZipFile:
                logger.error("Failed to extract SCORM package: Bad zip file")
                raise Http404("Failed to extract SCORM package: Bad zip file")

            return redirect('upload')
        logger.debug("No file found in POST request")
        return self.get(request)

class ScormPlayer(View):
    def get(self, request, pk):
        logger.debug(f"GET request received for ScormPlayer with pk: {pk}")
        try:
            scorm_package = ScormPackage.objects.get(pk=pk)
            logger.debug(f"SCORM package found: {scorm_package.title}")
            launch_url = scorm_package.get_launch_url()
            if launch_url:
                logger.debug(f"Launch URL found: {launch_url}")
                return render(request, 'scorm_app/player.html', {'scorm_id': pk})
            else:
                logger.error("Unable to find a suitable launch file for this SCORM package")
                raise Http404("Unable to find a suitable launch file for this SCORM package.")
        except ScormPackage.DoesNotExist:
            logger.error("SCORM package not found")
            raise Http404("SCORM package not found")

@method_decorator(xframe_options_exempt, name='dispatch')
class ServeScormContent(View):
    def get(self, request, pk, path):
        logger.debug(f"GET request received for ServeScormContent with pk: {pk} and path: {path}")
        try:
            scorm_package = ScormPackage.objects.get(pk=pk)
            logger.debug(f"SCORM package found: {scorm_package.title}")
            safe_title = scorm_package.title.replace(' ', '_')
            file_path = os.path.join(settings.MEDIA_ROOT, 'scorm_packages', safe_title, path)
            logger.debug(f"File path: {file_path}")
            if os.path.exists(file_path):
                logger.debug("File found, serving file")
                response = FileResponse(open(file_path, 'rb'))
                response['Access-Control-Allow-Origin'] = '*'
                response['X-Frame-Options'] = 'SAMEORIGIN'
                return response
            else:
                logger.error("File not found")
                raise Http404("File not found")
        except ScormPackage.DoesNotExist:
            logger.error("SCORM package not found")
            raise Http404("SCORM package not found")
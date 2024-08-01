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
        scorm_packages = ScormPackage.objects.all()
        return render(request, 'scorm_app/upload.html', {'scorm_packages': scorm_packages})

    def post(self, request):
        if 'file' in request.FILES:
            file = request.FILES['file']
            title = os.path.splitext(file.name)[0]
            safe_title = title.replace(' ', '_')
            scorm_package = ScormPackage.objects.create(title=title, file=file)

            # Log the created SCORM package
            logger.info(f'SCORM package created: {scorm_package.pk}, title: {scorm_package.title}')
            
            # Extract the SCORM package
            zip_path = os.path.join(settings.MEDIA_ROOT, scorm_package.file.name)
            extract_path = os.path.join(settings.MEDIA_ROOT, 'scorm_packages', safe_title)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            return redirect('upload')
        return self.get(request)

class ScormPlayer(View):
    def get(self, request, pk):
        try:
            scorm_package = ScormPackage.objects.get(pk=pk)
            launch_url = scorm_package.get_launch_url()
            if launch_url:
                return render(request, 'scorm_app/player.html', {'scorm_id': pk})
            else:
                raise Http404("Unable to find a suitable launch file for this SCORM package.")
        except ScormPackage.DoesNotExist:
            raise Http404("SCORM package not found")

@method_decorator(xframe_options_exempt, name='dispatch')
class ServeScormContent(View):
    def get(self, request, pk, path):
        scorm_package = ScormPackage.objects.get(pk=pk)
        safe_title = scorm_package.title.replace(' ', '_')
        file_path = os.path.join(settings.MEDIA_ROOT, 'scorm_packages', safe_title, path)
        if os.path.exists(file_path):
            response = FileResponse(open(file_path, 'rb'))
            response['Access-Control-Allow-Origin'] = '*'
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        raise Http404("File not found")
from django.urls import path
from .views import UploadScormPackage, ScormPlayer, ServeScormContent

urlpatterns = [
    path('', UploadScormPackage.as_view(), name='upload'),
    path('player/<int:pk>/', ScormPlayer.as_view(), name='player'),
    path('scorm_content/<int:pk>/<path:path>', ServeScormContent.as_view(), name='serve_scorm_content'),
]
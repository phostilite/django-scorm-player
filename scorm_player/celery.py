# celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scorm_player.settings')

app = Celery('scorm_player')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
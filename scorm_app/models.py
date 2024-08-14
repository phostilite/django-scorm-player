import os
import logging
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

class Course(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class SCORMStandard(models.Model):
    name = models.CharField(max_length=50, unique=True)
    version = models.CharField(max_length=20)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} - {self.version}"

class ScormPackage(models.Model):
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    scorm_standard = models.ForeignKey(SCORMStandard, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to='scorm_packages/')
    version = models.CharField(max_length=50)
    manifest_path = models.CharField(max_length=255)
    launch_path = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error')
    ], default='processing')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course.title} - {self.file.name}"

    def get_absolute_url(self):
        return reverse('launch_scorm', args=[str(self.id)])

    def get_launch_url(self):
        if self.launch_path:
            # Remove 'media/' from the beginning if it exists
            clean_path = self.launch_path.lstrip('media/')
            
            # Construct the correct URL using the MEDIA_URL setting
            return f"{settings.MEDIA_URL}{clean_path}"
        return None

    def get_full_launch_url(self):
        launch_url = self.get_launch_url()
        if launch_url:
            return f"{settings.BASE_URL.rstrip('/')}{launch_url}"
        return None

class UserCourseRegistration(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.course.title}"

class SCORMAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scorm_package = models.ForeignKey(ScormPackage, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(auto_now=True)
    completion_status = models.CharField(max_length=20, blank=True)
    success_status = models.CharField(max_length=20, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_complete = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.score is not None:
            self.score = max(0, min(100, self.score))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.scorm_package.file.name}"

    def update_status(self, completion_status=None, success_status=None, score=None):
        if completion_status:
            self.completion_status = completion_status
        if success_status:
            self.success_status = success_status
        if score is not None:
            self.score = score
        self.save()

class SCORMElement(models.Model):
    scorm_attempt = models.ForeignKey(SCORMAttempt, on_delete=models.CASCADE)
    element_id = models.CharField(max_length=255)
    value = models.TextField()
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('scorm_attempt', 'element_id')

    def __str__(self):
        return f"{self.scorm_attempt} - {self.element_id}"

class APIKeys(models.Model):
    lms_name = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.lms_name
    
class TaskResult(models.Model):
    task_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=50, default='PENDING')
    result = models.JSONField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_done = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Task {self.task_id}: {self.status}"

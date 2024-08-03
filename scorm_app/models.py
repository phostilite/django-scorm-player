import os
import logging
from django.db import models
from django.contrib.auth.models import User

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
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
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
        return self.file.name

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
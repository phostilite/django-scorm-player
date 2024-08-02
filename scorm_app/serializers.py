# serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Course, ScormPackage, UserCourseRegistration, SCORMAttempt, SCORMElement

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'created_at', 'is_active']

class ScormPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScormPackage
        fields = ['id', 'course', 'scorm_standard', 'file', 'version', 'manifest_path', 'launch_path', 'status', 'uploaded_at', 'created_at']

class UserCourseRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCourseRegistration
        fields = ['id', 'user', 'course', 'registered_at']

class SCORMAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCORMAttempt
        fields = ['id', 'user', 'scorm_package', 'started_at', 'last_accessed_at', 'completion_status', 'success_status', 'score', 'is_complete']

class SCORMElementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCORMElement
        fields = ['id', 'scorm_attempt', 'element_id', 'value', 'timestamp']
# views.py
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.shortcuts import render
from .models import Course, ScormPackage, UserCourseRegistration, SCORMAttempt, SCORMElement
from .serializers import (
    CourseSerializer, ScormPackageSerializer, UserCourseRegistrationSerializer,
    SCORMAttemptSerializer, SCORMElementSerializer, UserSerializer
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


from .tasks import process_scorm_package

logger = logging.getLogger(__name__)

class CustomTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        auth = request.headers.get('Authorization', '').split()

        if not auth or auth[0].lower() not in ['token', 'bearer']:
            return None

        if len(auth) == 1:
            raise AuthenticationFailed('Invalid token header. No credentials provided.')
        elif len(auth) > 2:
            raise AuthenticationFailed('Invalid token header. Token string should not contain spaces.')

        try:
            token = auth[1]
        except UnicodeError:
            raise AuthenticationFailed('Invalid token header. Token string should not contain invalid characters.')

        return self.authenticate_credentials(token)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action == 'create_user':
            return [AllowAny()]
        return super().get_permissions()
    
    @action(detail=False, methods=['post'])
    def create_user(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'user': serializer.data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

class ScormPackageViewSet(viewsets.ModelViewSet):
    queryset = ScormPackage.objects.all()
    serializer_class = ScormPackageSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def upload_package(self, request):
        try:
            course_id = request.data.get('course_id')
            file = request.FILES.get('file')
            
            if not course_id or not file:
                return Response({'error': 'Both course_id and file are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            course = get_object_or_404(Course, id=course_id)
            
            package = ScormPackage.objects.create(
                course=course,
                file=file,
                status='uploaded'
            )
            
            # Trigger the processing task
            process_scorm_package.delay(package.id)
            
            serializer = self.get_serializer(package)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error processing SCORM package: {str(e)}")
            return Response({'error': 'An error occurred while processing the package.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserCourseRegistrationViewSet(viewsets.ModelViewSet):
    queryset = UserCourseRegistration.objects.all()
    serializer_class = UserCourseRegistrationSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def register_user(self, request):
        user_id = request.data.get('user_id')
        course_id = request.data.get('course_id')
        user = get_object_or_404(User, id=user_id)
        course = get_object_or_404(Course, id=course_id)
        
        registration, created = UserCourseRegistration.objects.get_or_create(
            user=user, course=course
        )
        
        serializer = self.get_serializer(registration)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class SCORMAttemptViewSet(viewsets.ModelViewSet):
    queryset = SCORMAttempt.objects.all()
    serializer_class = SCORMAttemptSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def start_attempt(self, request):
        user_id = request.data.get('user_id')
        package_id = request.data.get('package_id')
        user = get_object_or_404(User, id=user_id)
        package = get_object_or_404(ScormPackage, id=package_id)
        
        attempt = SCORMAttempt.objects.create(user=user, scorm_package=package)
        serializer = self.get_serializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        attempt = self.get_object()
        serializer = self.get_serializer(attempt, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def start_session(self, request, pk=None):
        attempt = self.get_object()
        if attempt.user != request.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        login(request, attempt.user)
        return Response({"message": "Session started"})

    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        attempt = self.get_object()
        if attempt.user != request.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        logout(request)
        return Response({"message": "Session ended"})

class SCORMElementViewSet(viewsets.ModelViewSet):
    queryset = SCORMElement.objects.all()
    serializer_class = SCORMElementSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def update_element(self, request):
        attempt_id = request.data.get('attempt_id')
        element_id = request.data.get('element_id')
        value = request.data.get('value')
        
        attempt = get_object_or_404(SCORMAttempt, id=attempt_id)
        element, created = SCORMElement.objects.update_or_create(
            scorm_attempt=attempt,
            element_id=element_id,
            defaults={'value': value}
        )
        
        serializer = self.get_serializer(element)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class SCORMAPIViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def set_value(self, request):
        attempt_id = request.data.get('attempt_id')
        element_id = request.data.get('element_id')
        value = request.data.get('value')
        
        attempt = get_object_or_404(SCORMAttempt, id=attempt_id, user=request.user)
        element, _ = SCORMElement.objects.update_or_create(
            scorm_attempt=attempt,
            element_id=element_id,
            defaults={'value': value}
        )
        return Response({"success": True})

    @action(detail=False, methods=['get'])
    def get_value(self, request):
        attempt_id = request.query_params.get('attempt_id')
        element_id = request.query_params.get('element_id')
        
        attempt = get_object_or_404(SCORMAttempt, id=attempt_id, user=request.user)
        element = get_object_or_404(SCORMElement, scorm_attempt=attempt, element_id=element_id)
        return Response({"value": element.value})

class ReportingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['get'])
    def user_course_report(self, request):
        user_id = request.query_params.get('user_id')
        course_id = request.query_params.get('course_id')
        
        user = get_object_or_404(User, id=user_id)
        course = get_object_or_404(Course, id=course_id)
        
        attempts = SCORMAttempt.objects.filter(user=user, scorm_package__course=course)
        
        report_data = {
            'user': UserSerializer(user).data,
            'course': CourseSerializer(course).data,
            'attempts': SCORMAttemptSerializer(attempts, many=True).data,
        }
        
        return Response(report_data)

def launch_scorm(request, attempt_id):
    attempt = get_object_or_404(SCORMAttempt, id=attempt_id, user=5)
    package = attempt.scorm_package
    
    context = {
        'attempt': attempt,
        'package': package,
        'launch_url': f'/media/scorm_extracted/{package.id}/index_lms.html',
    }
    return render(request, 'scorm_app/player.html', context)
import logging
from rest_framework import viewsets, status, serializers, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404, render
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from celery.result import AsyncResult
from django.db import transaction
from .models import Course, ScormPackage, UserCourseRegistration, SCORMAttempt, SCORMElement
from .serializers import (
    CourseSerializer, ScormPackageSerializer, UserCourseRegistrationSerializer,
    SCORMAttemptSerializer, SCORMElementSerializer, UserSerializer
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from .tasks import process_scorm_package

logger = logging.getLogger(__name__)

class CustomTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        auth = request.headers.get('Authorization', '').split()

        if not auth or auth[0].lower() not in ['token', 'bearer']:
            return None

        if len(auth) == 1:
            msg = 'Invalid token header. No credentials provided.'
            raise AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = 'Invalid token header. Token string should not contain spaces.'
            raise AuthenticationFailed(msg)

        try:
            token = auth[1]
        except UnicodeError:
            msg = 'Invalid token header. Token string should not contain invalid characters.'
            raise AuthenticationFailed(msg)

        return self.authenticate_credentials(token)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = [CustomTokenAuthentication]
    
    def get_permissions(self):
        if self.action in ['create', 'validate_user']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def create(self, request):
        logger.info("Attempting to create a new user")
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            logger.info(f"User created successfully: {user.username}")
            return Response({
                'user': serializer.data,
                'token': token.key
            }, status=status.HTTP_201_CREATED)
        except serializers.ValidationError as e:
            logger.error(f"User creation failed: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error during user creation: {str(e)}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], authentication_classes=[])
    def validate_user(self, request):
        logger.info("Attempting to validate user")
        username = request.data.get('username')
        email = request.data.get('email')

        if not username or not email:
            logger.error("Missing username or email in request")
            return Response({'error': 'Both username and email are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(username=username, email=email)
            logger.info(f"User validated successfully: {username}")
            return Response({
                'exists': True,
                'user_id': user.id
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            logger.info(f"User not found: {username}")
            return Response({
                'exists': False
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error validating user: {str(e)}")
            return Response({'error': 'An error occurred while validating the user.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request):
        # Optionally restrict this to admin users
        if not request.user.is_staff:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request)

    def retrieve(self, request, pk=None):
        # Optionally restrict this to admin users or the user themselves
        user = self.get_object()
        if not request.user.is_staff and request.user.id != user.id:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        return super().retrieve(request, pk)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def destroy(self, request, pk=None):
        # Optionally restrict this to admin users
        if not request.user.is_staff:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, pk)

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    def list(self, request):
        logger.info("Fetching list of courses")
        courses = self.get_queryset()
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        logger.info(f"Fetching course with id: {pk}")
        course = get_object_or_404(Course, pk=pk)
        serializer = self.get_serializer(course)
        return Response(serializer.data)

class ScormPackageViewSet(viewsets.ModelViewSet):
    queryset = ScormPackage.objects.all()
    serializer_class = ScormPackageSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def upload_package(self, request):
        logger.info("Attempting to upload a SCORM package")
        try:
            course_id = request.data.get('course_id')
            file = request.FILES.get('file')
            
            if not course_id or not file:
                logger.error("Missing course_id or file in request")
                return Response({'error': 'Both course_id and file are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            course = get_object_or_404(Course, id=course_id)
            
            with transaction.atomic():
                package = ScormPackage.objects.create(
                    course=course,
                    file=file,
                    status='uploaded'
                )
            
            # Trigger the processing task
            task = process_scorm_package.delay(package.id)
            
            serializer = self.get_serializer(package)
            logger.info(f"SCORM package uploaded successfully for course: {course_id}")
            return Response({
                'package': serializer.data,
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            logger.error(f"Error processing SCORM package: {str(e)}")
            return Response({'error': 'An error occurred while processing the package.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def check_status(self, request):
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'error': 'task_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        task_result = AsyncResult(task_id)
        if task_result.ready():
            try:
                package = ScormPackage.objects.get(id=task_result.result)
                serializer = self.get_serializer(package)
                return Response(serializer.data)
            except ScormPackage.DoesNotExist:
                return Response({'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'status': 'processing'}, status=status.HTTP_202_ACCEPTED)

class UserCourseRegistrationViewSet(viewsets.ModelViewSet):
    queryset = UserCourseRegistration.objects.all()
    serializer_class = UserCourseRegistrationSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def register_for_course(self, request):
        logger.info("Attempting to register user for a course")
        user_id = request.data.get('user_id')
        course_id = request.data.get('course_id')
        
        if not user_id or not course_id:
            logger.error("Missing user_id or course_id in request")
            return Response({'error': 'Both user_id and course_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = get_object_or_404(User, id=user_id)
        course = get_object_or_404(Course, id=course_id)
        
        try:
            with transaction.atomic():
                registration, created = UserCourseRegistration.objects.get_or_create(
                    user=user, course=course
                )
            
            serializer = self.get_serializer(registration)
            logger.info(f"User {user_id} registered for course {course_id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error registering user for course: {str(e)}")
            return Response({'error': 'An error occurred while registering for the course.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SCORMAttemptViewSet(viewsets.ModelViewSet):
    queryset = SCORMAttempt.objects.all()
    serializer_class = SCORMAttemptSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def start_attempt(self, request):
        logger.info("Attempting to start a new SCORM attempt")
        user_id = request.data.get('user_id')
        package_id = request.data.get('package_id')
        
        if not user_id or not package_id:
            logger.error("Missing user_id or package_id in request")
            return Response({'error': 'Both user_id and package_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = get_object_or_404(User, id=user_id)
        package = get_object_or_404(ScormPackage, id=package_id)
        
        try:
            with transaction.atomic():
                attempt = SCORMAttempt.objects.create(user=user, scorm_package=package)
            serializer = self.get_serializer(attempt)
            logger.info(f"SCORM attempt started for user {user_id} on package {package_id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error starting SCORM attempt: {str(e)}")
            return Response({'error': 'An error occurred while starting the attempt.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        logger.info(f"Updating progress for SCORM attempt {pk}")
        attempt = self.get_object()
        serializer = self.get_serializer(attempt, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info(f"Progress updated for SCORM attempt {pk}")
            return Response(serializer.data)
        except ValidationError as e:
            logger.error(f"Error updating SCORM attempt progress: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def start_session(self, request, pk=None):
        logger.info(f"Starting session for SCORM attempt {pk}")
        attempt = self.get_object()
        if attempt.user != request.user:
            logger.warning(f"Unauthorized access attempt for SCORM attempt {pk}")
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        login(request, attempt.user)
        logger.info(f"Session started for SCORM attempt {pk}")
        return Response({"message": "Session started"})

    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        logger.info(f"Ending session for SCORM attempt {pk}")
        attempt = self.get_object()
        if attempt.user != request.user:
            logger.warning(f"Unauthorized access attempt for SCORM attempt {pk}")
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        logout(request)
        logger.info(f"Session ended for SCORM attempt {pk}")
        return Response({"message": "Session ended"})

class SCORMElementViewSet(viewsets.ModelViewSet):
    queryset = SCORMElement.objects.all()
    serializer_class = SCORMElementSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def update_element(self, request):
        logger.info("Updating SCORM element")
        attempt_id = request.data.get('attempt_id')
        element_id = request.data.get('element_id')
        value = request.data.get('value')
        
        if not all([attempt_id, element_id, value]):
            logger.error("Missing required data for updating SCORM element")
            return Response({'error': 'attempt_id, element_id, and value are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            attempt = get_object_or_404(SCORMAttempt, id=attempt_id)
            element, created = SCORMElement.objects.update_or_create(
                scorm_attempt=attempt,
                element_id=element_id,
                defaults={'value': value}
            )
            
            serializer = self.get_serializer(element)
            logger.info(f"SCORM element updated: {element_id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error updating SCORM element: {str(e)}")
            return Response({'error': 'An error occurred while updating the SCORM element.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SCORMAPIViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['post'])
    def set_value(self, request):
        logger.info("Setting SCORM API value")
        attempt_id = request.data.get('attempt_id')
        element_id = request.data.get('element_id')
        value = request.data.get('value')
        
        if not all([attempt_id, element_id, value]):
            logger.error("Missing required data for setting SCORM API value")
            return Response({'error': 'attempt_id, element_id, and value are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            attempt = get_object_or_404(SCORMAttempt, id=attempt_id, user=request.user)
            element, _ = SCORMElement.objects.update_or_create(
                scorm_attempt=attempt,
                element_id=element_id,
                defaults={'value': value}
            )
            
            # Update SCORMAttempt if necessary
            if element_id in ['cmi.core.lesson_status', 'cmi.completion_status']:
                attempt.update_status(completion_status=value)
            elif element_id in ['cmi.core.score.raw', 'cmi.score.raw']:
                attempt.update_status(score=float(value))
            
            logger.info(f"SCORM API value set: {element_id}")
            return Response({"success": True})
        except Exception as e:
            logger.error(f"Error setting SCORM API value: {str(e)}")
            return Response({'error': 'An error occurred while setting the SCORM API value.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_value(self, request):
        logger.info("Getting SCORM API value")
        attempt_id = request.query_params.get('attempt_id')
        element_id = request.query_params.get('element_id')
        
        if not all([attempt_id, element_id]):
            logger.error("Missing required data for getting SCORM API value")
            return Response({'error': 'attempt_id and element_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            attempt = get_object_or_404(SCORMAttempt, id=attempt_id, user=request.user)
            element = get_object_or_404(SCORMElement, scorm_attempt=attempt, element_id=element_id)
            logger.info(f"SCORM API value retrieved: {element_id}")
            return Response({"value": element.value})
        except SCORMElement.DoesNotExist:
            logger.warning(f"SCORM element not found: {element_id}")
            return Response({"value": ""})  # Return empty string for unset values
        except Exception as e:
            logger.error(f"Error getting SCORM API value: {str(e)}")
            return Response({'error': 'An error occurred while getting the SCORM API value.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReportingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomTokenAuthentication]

    @action(detail=False, methods=['get'])
    def user_course_report(self, request):
        logger.info("Generating user course report")
        user_id = request.query_params.get('user_id')
        course_id = request.query_params.get('course_id')
        
        if not all([user_id, course_id]):
            logger.error("Missing required data for generating user course report")
            return Response({'error': 'user_id and course_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = get_object_or_404(User, id=user_id)
            course = get_object_or_404(Course, id=course_id)
            
            attempts = SCORMAttempt.objects.filter(user=user, scorm_package__course=course)
            
            report_data = {
                'user': UserSerializer(user).data,
                'course': CourseSerializer(course).data,
                'attempts': SCORMAttemptSerializer(attempts, many=True).data,
            }
            
            logger.info(f"User course report generated for user {user_id} and course {course_id}")
            return Response(report_data)
        except Exception as e:
            logger.error(f"Error generating user course report: {str(e)}")
            return Response({'error': 'An error occurred while generating the report.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def launch_scorm(request, attempt_id):
    logger.info(f"Launching SCORM for attempt {attempt_id}")
    try:
        attempt = get_object_or_404(SCORMAttempt, id=attempt_id, user=request.user)
        package = attempt.scorm_package
        
        launch_url = package.get_launch_url()
        if not launch_url:
            logger.error(f"Launch URL not found for SCORM package {package.id}")
            return render(request, 'scorm_app/error.html', {'error': 'Launch URL not found for this SCORM package.'})
        
        context = {
            'attempt': attempt,
            'package': package,
            'launch_url': launch_url,
        }
        logger.info(f"SCORM launched successfully for attempt {attempt_id}")
        return render(request, 'scorm_app/player.html', context)
    except SCORMAttempt.DoesNotExist:
        logger.error(f"SCORM attempt {attempt_id} not found")
        return render(request, 'scorm_app/error.html', {'error': 'SCORM attempt not found.'})
    except Exception as e:
        logger.error(f"Error launching SCORM for attempt {attempt_id}: {str(e)}")
        return render(request, 'scorm_app/error.html', {'error': 'An error occurred while launching the SCORM package.'})
    

@api_view(['POST'])
@permission_classes([AllowAny])
def test_validate_user(request):
    return Response({'message': 'Test endpoint reached'})
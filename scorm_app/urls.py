from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, CourseViewSet, ScormPackageViewSet, UserCourseRegistrationViewSet, SCORMAttemptViewSet, SCORMElementViewSet, SCORMAPIViewSet, ReportingViewSet, launch_scorm, test_connection
from rest_framework.authtoken.views import obtain_auth_token

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'scorm-packages', ScormPackageViewSet)
router.register(r'registrations', UserCourseRegistrationViewSet)
router.register(r'attempts', SCORMAttemptViewSet)
router.register(r'elements', SCORMElementViewSet)
router.register(r'scorm-api', SCORMAPIViewSet, basename='scorm-api')
router.register(r'reports', ReportingViewSet, basename='reports')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/api-token-auth/', obtain_auth_token, name='api_token_auth'),
    path('api/test-connection/', test_connection, name='test_connection'),

    path('launch/<int:attempt_id>/', launch_scorm, name='launch_scorm'),
]
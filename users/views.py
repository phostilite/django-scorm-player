from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from scorm_app.models import UserCourseRegistration, SCORMAttempt, Course

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(reverse('user_dashboard'))
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'users/login.html')

def user_logout(request):
    logout(request)
    return redirect(reverse('user_login'))
        
@login_required
def user_dashboard(request):
    user = request.user
    
    # Get user's registered courses
    registered_courses = UserCourseRegistration.objects.filter(user=user).select_related('course')
    
    # Get user's SCORM attempts
    scorm_attempts = SCORMAttempt.objects.filter(user=user).select_related('scorm_package__course')
    
    # Get all available courses
    all_courses = Course.objects.filter(is_active=True)
    
    context = {
        'user': user,
        'registered_courses': registered_courses,
        'scorm_attempts': scorm_attempts,
        'all_courses': all_courses,
    }
    
    return render(request, 'users/home.html', context)


def user_signup(request):
    return render(request, 'users/signup.html')
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
from django.template.loader import render_to_string

from .models import UserProfile, UserRegistration

logger = logging.getLogger(__name__)


def get_from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', 'noreply@fraudguard.local')


def get_clean_username(user):
    if not user:
        return "Customer"
    username = getattr(user, 'username', '') or ''
    if '@' in username:
        return username.split('@')[0]
    return username


def send_welcome_email(user, request=None):
    if not user or not user.email:
        return
    subject = "🛡️ Welcome to FraudGuard Cyber Defense Portal"
    from_email = get_from_email()
    to_email = [user.email]

    clean_name = user.first_name or get_clean_username(user)
    context = {
        'user': user,
        'clean_name': clean_name,
        'portal_url': request.build_absolute_uri('/') if request else 'http://127.0.0.1:8000/',
    }

    try:
        html_content = render_to_string('account/welcome_email.html', context)
        text_content = strip_tags(html_content)
        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        logger.warning(f"Error sending welcome email to {user.email}: {e}")


def send_password_reset_email_custom(user, reset_url):
    if not user or not user.email:
        return
    subject = "🔑 FraudGuard Password Reset Authorization"
    from_email = get_from_email()
    to_email = [user.email]
    context = {
        'user': user,
        'display_username': user.first_name or get_clean_username(user),
        'reset_url': reset_url,
    }
    try:
        html_content = render_to_string('account/password_reset_email.html', context)
        text_content = strip_tags(html_content)
        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        logger.warning(f"Error sending password reset email to {user.email}: {e}")


# ===========================================================================
# Unified Authentication Views (Detector + Arrestor Roles)
# ===========================================================================

def user_register(request):
    """
    Unified Registration:
    Allows user to select their role (Detector or Arrestor).
    Logs in and directs user to their specific portal.
    """
    if request.user.is_authenticated:
        role = getattr(getattr(request.user, 'profile', None), 'role', 'detector')
        return redirect('arrestor_home' if role == 'arrestor' else 'home')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        role = request.POST.get('role', 'detector').strip().lower()
        if role not in ['detector', 'arrestor']:
            role = 'detector'

        if not username or not email or not password or not first_name or not last_name:
            messages.error(request, "All fields (First Name, Last Name, Username, Email, Password) are required.")
            return render(request, 'account/register.html')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'account/register.html')

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return render(request, 'account/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken. Please choose another.")
            return render(request, 'account/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email address already exists.")
            return render(request, 'account/register.html')

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Create Profile with chosen role
        UserProfile.objects.create(user=user, role=role)

        # Sync UserRegistration
        try:
            UserRegistration.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'password': user.password,
                    'role': role,
                }
            )
        except Exception as e:
            logger.warning(f"Sync error to UserRegistration: {e}")

        # Dispatch Welcome Email
        send_welcome_email(user, request=request)

        # Log user in
        login(request, user)
        name_display = user.get_full_name() or user.username

        if role == 'arrestor':
            messages.success(request, f"⚖️ Welcome Officer {name_display}! You have been registered and granted access to the Fraud Arrestor Case Resolution Desk.")
            return redirect('arrestor_home')
        else:
            messages.success(request, f"🎉 Welcome to FraudGuard, {name_display}! Your Threat Detector account is ready.")
            return redirect('home')

    return render(request, 'account/register.html')


def user_login(request):
    """
    Unified Login:
    Authenticates user and auto-routes based on their role:
    - arrestor role -> /arrestor/
    - detector role -> /
    """
    if request.user.is_authenticated:
        role = getattr(getattr(request.user, 'profile', None), 'role', 'detector')
        return redirect('arrestor_home' if role == 'arrestor' else 'home')

    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        login_input = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = None
        if '@' in login_input:
            matched_user = User.objects.filter(email=login_input).first()
            if matched_user:
                user = authenticate(request, username=matched_user.username, password=password)
        else:
            user = authenticate(request, username=login_input, password=password)

        if user is not None:
            login(request, user)
            profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'detector'})
            role = profile.role

            if next_url and next_url not in ['home', '/']:
                return redirect(next_url)

            if role == 'arrestor':
                messages.success(request, f"⚖️ Welcome back, Officer {user.username}! Fraud Arrestor Panel loaded.")
                return redirect('arrestor_home')
            else:
                messages.success(request, f"🛡️ Welcome back, {user.username}!")
                return redirect('home')
        else:
            messages.error(request, "Invalid username/email or password.")

    return render(request, 'account/login.html', {'next': next_url or 'home'})


def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()

        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = request.build_absolute_uri(
                reverse('reset_password_confirm', kwargs={'uidb64': uid, 'token': token})
            )
            send_password_reset_email_custom(user, reset_url)

        messages.success(
            request,
            "If an account exists with that email, a password reset link has been dispatched to your inbox."
        )
        return render(request, 'account/forgot_password_done.html')

    return render(request, 'account/forgot_password.html')


def reset_password_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password = request.POST.get('password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return render(request, 'account/reset_password_confirm.html', {'validlink': True})

            if len(new_password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return render(request, 'account/reset_password_confirm.html', {'validlink': True})

            user.set_password(new_password)
            user.save()
            messages.success(request, "Your password has been reset successfully! You can now sign in.")
            return redirect('login')

        return render(request, 'account/reset_password_confirm.html', {'validlink': True})

    messages.error(request, "The password reset link is invalid or has expired.")
    return render(request, 'account/reset_password_confirm.html', {'validlink': False})

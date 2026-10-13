import re
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
from django.template.loader import render_to_string
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import UserRegistration, UserProfile, TransactionCheck, EmailFraudCheck, CallFraudCheck, MessageFraudCheck
from .serializers import (
    TransactionCheckSerializer,
    EmailFraudCheckSerializer,
    CallFraudCheckSerializer,
    MessageFraudCheckSerializer,
)

logger = logging.getLogger(__name__)


def get_risk_level_from_score(risk_score, is_fraud=False):
    if risk_score >= 60 or is_fraud:
        return 'HIGH'
    elif risk_score >= 30:
        return 'MEDIUM'
    return 'LOW'


# ---------------------------------------------------------------------------
# Email Dispatchers (Directly in views.py)
# ---------------------------------------------------------------------------

def get_from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', 'noreply@fraudguard.local')


def get_clean_username(user):
    """
    Returns clean username without email domain, even if user registered with email as username.
    """
    if not user:
        return "Customer"
    username = getattr(user, 'username', '') or ''
    if '@' in username:
        return username.split('@')[0]
    return username


def send_welcome_email(user, request=None):
    """
    Sends a formatted welcome email upon successful user registration using welcome_email.html template.
    """
    if not user.email:
        return

    subject = "🛡️ Welcome to FraudGuard - Your Security Account is Ready!"
    from_email = get_from_email()
    to_email = [user.email]

    dashboard_url = 'http://127.0.0.1:8000/'
    if request:
        try:
            dashboard_url = request.build_absolute_uri('/')
        except Exception:
            dashboard_url = 'http://127.0.0.1:8000/'

    display_username = get_clean_username(user)

    context = {
        'user': user,
        'display_username': display_username,
        'dashboard_url': dashboard_url,
    }

    try:
        html_content = render_to_string('detector/welcome_email.html', context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        logger.warning(f"Error sending welcome email to {user.email}: {e}")


def send_fraud_alert_email(fraud_type, details_dict, risk_score, reasons, user=None):
    """
    Dispatches a high-priority fraud alert email to the user and admin using fraud_alert_email.html.
    """
    subject = f"🚨 [FraudGuard Alert] High-Risk Fraud Detected ({fraud_type} - {risk_score}%)"
    from_email = get_from_email()
    recipients = set()

    # Admin email
    admin_email = getattr(settings, 'EMAIL_HOST_USER', None)
    if admin_email and '@' in admin_email:
        recipients.add(admin_email)

    # Logged-in user email
    if user and user.email and '@' in user.email:
        recipients.add(user.email)

    # Target email from form if present
    target_email = details_dict.get('Customer Email') or details_dict.get('Sender Email')
    if target_email and '@' in target_email:
        recipients.add(target_email)

    if not recipients:
        return

    username_display = get_clean_username(user)

    context = {
        'fraud_type': fraud_type,
        'risk_score': risk_score,
        'details_dict': details_dict,
        'reasons': reasons,
        'username_display': username_display,
        'display_username': username_display,
    }

    try:
        html_content = render_to_string('detector/fraud_alert_email.html', context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(subject, text_content, from_email, list(recipients))
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        logger.warning(f"Error sending fraud alert email: {e}")


def send_password_reset_email_custom(user, reset_url):
    """
    Sends a formatted password reset recovery email using password_reset_email.html.
    """
    if not user.email:
        return

    subject = "🔑 FraudGuard - Reset Your Account Password"
    from_email = get_from_email()
    to_email = [user.email]

    context = {
        'user': user,
        'display_username': get_clean_username(user),
        'reset_url': reset_url,
    }

    try:
        html_content = render_to_string('detector/password_reset_email.html', context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        logger.warning(f"Error sending password reset email to {user.email}: {e}")


def send_log_deletion_email(user, log_type, item_info):
    """
    Sends confirmation when a user deletes a scan log from their history using log_deletion_email.html.
    """
    if not user or not user.email:
        return

    subject = f"🗑️ FraudGuard Notice - Scan Log Removed ({log_type})"
    from_email = get_from_email()
    to_email = [user.email]

    context = {
        'user': user,
        'display_username': get_clean_username(user),
        'log_type': log_type,
        'item_info': item_info,
    }

    try:
        html_content = render_to_string('detector/log_deletion_email.html', context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        logger.warning(f"Error sending deletion confirmation email: {e}")


# ---------------------------------------------------------------------------
# Fraud Analysis Algorithms
# ---------------------------------------------------------------------------

def analyze_transaction_fraud(email, amount_str, card_number, user=None):
    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        amount = 0.0

    risk_score = 0
    reasons = []

    if amount > 100000:
        risk_score += 40
        reasons.append("High transaction amount (Above ₹1,00,000)")
    elif amount > 50000:
        risk_score += 20
        reasons.append("Elevated transaction amount (Above ₹50,000)")

    suspicious_domains = ['fake.com', 'test.com', 'tempmail.com', 'trashmail.com', 'mailinator.com', 'guerrillamail.com']
    if any(domain in (email or '').lower() for domain in suspicious_domains):
        risk_score += 40
        reasons.append("Suspicious or disposable email domain")

    clean_card = (card_number or '').strip().replace(' ', '').replace('-', '')
    if len(clean_card) != 16 or not clean_card.isdigit():
        risk_score += 25
        reasons.append("Invalid card number format (Must be exactly 16 numeric digits)")

    if clean_card in ['1234567812345678', '0000000000000000', '1111111111111111']:
        risk_score += 35
        reasons.append("Known test/dummy card pattern detected")

    risk_score = min(risk_score, 100)
    is_fraud = risk_score >= 50

    if is_fraud:
        send_fraud_alert_email(
            "Transaction Fraud",
            {
                "Customer Email": email,
                "Amount": f"₹{amount}",
                "Card Number": f"****{clean_card[-4:]}" if len(clean_card) >= 4 else clean_card,
            },
            risk_score,
            reasons,
            user=user
        )

    return is_fraud, risk_score, reasons, amount


def analyze_email_fraud(sender_email, subject, body_text, user=None):
    risk_score = 0
    reasons = []
    combined_text = f"{subject} {body_text}".lower()

    suspicious_domains = [
        'fake.com', 'tempmail.com', 'trashmail.com', 'mailinator.com', 'guerrillamail.com',
        'paypal-support.xyz', 'sbi-alert.top', 'hdfc-verification.info', 'tax-refund.top'
    ]
    if any(domain in (sender_email or '').lower() for domain in suspicious_domains):
        risk_score += 40
        reasons.append("Known disposable or spoofed email domain")

    phishing_keywords = [
        'verify your account', 'account suspended', 'unauthorized access', 'click here to login',
        'password expired', 'immediate action required', 'kyc verification pending', 'wire transfer',
        'lottery winner', 'won prize', 'income tax refund', 'update pan card', 'reset password urgently'
    ]
    matched_keywords = [kw for kw in phishing_keywords if kw in combined_text]
    if matched_keywords:
        risk_score += min(len(matched_keywords) * 20, 50)
        reasons.append(f"High-risk phishing keywords found: {', '.join(matched_keywords[:3])}")

    url_pattern = r'https?://[^\s]+'
    found_urls = re.findall(url_pattern, combined_text)
    if found_urls:
        shorteners = ['bit.ly', 'tinyurl', 't.co', 'cutt.ly', 'is.gd', 'shorturl.at']
        if any(any(s in url for s in shorteners) for url in found_urls):
            risk_score += 30
            reasons.append("Shortened / obfuscated URL detected")
        if any(re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', url) for url in found_urls):
            risk_score += 35
            reasons.append("Raw IP address used in link (common phishing trait)")

    urgency_words = ['within 24 hours', 'within 12 hours', 'immediately', 'act now', 'last warning']
    if any(u in combined_text for u in urgency_words):
        risk_score += 15
        reasons.append("High urgency pressure tactics detected")

    risk_score = min(risk_score, 100)
    is_fraud = risk_score >= 50

    if is_fraud:
        send_fraud_alert_email(
            "Email Phishing Fraud",
            {
                "Sender Email": sender_email,
                "Subject": subject or "(No Subject)",
                "Excerpt": (body_text or '')[:120],
            },
            risk_score,
            reasons,
            user=user
        )

    return is_fraud, risk_score, reasons


def analyze_call_fraud(phone_number, call_context, user=None):
    risk_score = 0
    reasons = []
    clean_number = (phone_number or '').strip().replace(' ', '').replace('-', '')
    context_lower = (call_context or '').lower()

    suspicious_prefixes = ['+234', '+252', '+92', '+880', '+4470', '+1809', '+1876']
    if any(clean_number.startswith(p) for p in suspicious_prefixes):
        risk_score += 40
        reasons.append("High-risk international caller prefix (Wangiri/Scam prone)")

    if len(clean_number) > 5 and len(set(clean_number.replace('+', ''))) <= 2:
        risk_score += 35
        reasons.append("Spoofed or repetitive number pattern")

    scam_keywords = [
        'cbi officer', 'mumbai police', 'delhi police', 'customs department', 'parcel seized',
        'drugs found', 'digital arrest', 'electricity bill unpaid', 'power cut tonight',
        'credit card reward points', 'kbc lucky winner', 'share otp', 'download anydesk',
        'download teamviewer', 'rustdesk', 'sim block', 'aadhar suspend'
    ]
    matched = [kw for kw in scam_keywords if kw in context_lower]
    if matched:
        risk_score += min(len(matched) * 25, 60)
        reasons.append(f"Impersonation/Scam call dialogue detected: {', '.join(matched[:3])}")

    if 'otp' in context_lower or 'transfer money' in context_lower:
        risk_score += 25
        reasons.append("Caller requested confidential OTP or immediate fund transfer")

    risk_score = min(risk_score, 100)
    is_fraud = risk_score >= 50

    if is_fraud:
        send_fraud_alert_email(
            "Fraudulent Call",
            {
                "Phone Number": phone_number,
                "Context": (call_context or '')[:120],
            },
            risk_score,
            reasons,
            user=user
        )

    return is_fraud, risk_score, reasons


def analyze_message_fraud(sender_info, message_text, user=None):
    risk_score = 0
    reasons = []
    text_lower = (message_text or '').lower()
    sender_clean = (sender_info or '').strip()

    if sender_clean.startswith('+') and not sender_clean.startswith('+91'):
        risk_score += 20
        reasons.append("International sender for domestic-style alert")

    sms_scam_keywords = [
        'electricity will be disconnected', 'power cutoff tonight', 'pan card update',
        'kyc expired', 'account will be blocked', 'part time job', 'earn daily 5000',
        'telegram task', 'won lottery', 'claim reward points', 'pre-approved loan of',
        'download apk', 'install file', 'send otp', 'share your otp', 'congratulations you won'
    ]
    matched = [kw for kw in sms_scam_keywords if kw in text_lower]
    if matched:
        risk_score += min(len(matched) * 25, 55)
        reasons.append(f"Scam SMS trigger words found: {', '.join(matched[:3])}")

    shorteners = ['bit.ly', 'tinyurl', 't.co', 'cutt.ly', 'is.gd', 'wa.me', 't.me', '.apk']
    if any(s in text_lower for s in shorteners):
        risk_score += 35
        reasons.append("Contains suspicious link, APK download, or chat redirect")

    if any(u in text_lower for u in ['call immediately', 'contact officer', 'within 2 hours', 'urgent']):
        risk_score += 15
        reasons.append("High urgency pressure in message")

    risk_score = min(risk_score, 100)
    is_fraud = risk_score >= 50

    if is_fraud:
        send_fraud_alert_email(
            "Fraudulent SMS / Message",
            {
                "Sender Info": sender_info,
                "Message Preview": (message_text or '')[:120],
            },
            risk_score,
            reasons,
            user=user
        )

    return is_fraud, risk_score, reasons


# ---------------------------------------------------------------------------
# Dashboard Home View
# ---------------------------------------------------------------------------

def home(request):
    """
    Publicly visible: Guests can browse the portal.
    If authenticated, displays the user's scan history with delete actions.
    """
    active_tab = request.GET.get('tab', 'transaction')

    if request.user.is_authenticated:
        if request.user.is_superuser:
            transaction_history = TransactionCheck.objects.all().order_by('-checked_at')[:15]
            email_history = EmailFraudCheck.objects.all().order_by('-checked_at')[:15]
            call_history = CallFraudCheck.objects.all().order_by('-checked_at')[:15]
            message_history = MessageFraudCheck.objects.all().order_by('-checked_at')[:15]
        else:
            transaction_history = TransactionCheck.objects.filter(user=request.user).order_by('-checked_at')[:15]
            email_history = EmailFraudCheck.objects.filter(user=request.user).order_by('-checked_at')[:15]
            call_history = CallFraudCheck.objects.filter(user=request.user).order_by('-checked_at')[:15]
            message_history = MessageFraudCheck.objects.filter(user=request.user).order_by('-checked_at')[:15]
    else:
        # Guests can see public demo records
        transaction_history = TransactionCheck.objects.all().order_by('-checked_at')[:5]
        email_history = EmailFraudCheck.objects.all().order_by('-checked_at')[:5]
        call_history = CallFraudCheck.objects.all().order_by('-checked_at')[:5]
        message_history = MessageFraudCheck.objects.all().order_by('-checked_at')[:5]

    return render(request, 'detector/index.html', {
        'active_tab': active_tab,
        'transaction_history': transaction_history,
        'email_history': email_history,
        'call_history': call_history,
        'message_history': message_history,
        'history': transaction_history,
    })


# ---------------------------------------------------------------------------
# Form Submissions (Require Authentication)
# ---------------------------------------------------------------------------

def form_submit(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.warning(request, "⚠️ Login required: Please sign in or register to scan transactions.")
            return redirect(f"{reverse('login')}?next={reverse('home')}?tab=transaction")

        email = request.POST.get('email', '')
        amount_str = request.POST.get('amount', 0)
        card_number = request.POST.get('card_number', '')
        ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')

        is_fraud, risk_score, reasons, amount = analyze_transaction_fraud(email, amount_str, card_number, user=request.user)
        risk_level = get_risk_level_from_score(risk_score, is_fraud)

        TransactionCheck.objects.create(
            user=request.user,
            user_email=email,
            amount=amount,
            card_number=card_number,
            ip_address=ip_address,
            is_fraud=is_fraud,
            risk_score=risk_score,
            risk_level=risk_level,
        )
        if is_fraud:
            messages.error(request, f"🚨 Threat Flagged! Transaction flagged with {risk_score}% risk. An alert email was sent to {request.user.email}.")
        else:
            messages.success(request, "✅ Transaction analysis complete: Flagged as safe.")

    return redirect('/?tab=transaction')


def submit_email(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.warning(request, "⚠️ Login required: Please sign in or register to scan emails for phishing.")
            return redirect(f"{reverse('login')}?next={reverse('home')}?tab=email")

        sender_email = request.POST.get('sender_email', '')
        subject = request.POST.get('subject', '')
        body_text = request.POST.get('body_text', '')

        is_fraud, risk_score, reasons = analyze_email_fraud(sender_email, subject, body_text, user=request.user)
        risk_level = get_risk_level_from_score(risk_score, is_fraud)

        EmailFraudCheck.objects.create(
            user=request.user,
            sender_email=sender_email,
            subject=subject,
            body_text=body_text,
            is_fraud=is_fraud,
            risk_score=risk_score,
            risk_level=risk_level,
            detected_reasons="; ".join(reasons)
        )
        if is_fraud:
            messages.error(request, f"🚨 Phishing Alert! Email flagged with {risk_score}% risk. Alert sent to {request.user.email}.")
        else:
            messages.success(request, "✅ Email analysis complete: Content appears legitimate.")

    return redirect('/?tab=email')


def submit_call(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.warning(request, "⚠️ Login required: Please sign in or register to scan phone numbers and call risks.")
            return redirect(f"{reverse('login')}?next={reverse('home')}?tab=call")

        phone_number = request.POST.get('phone_number', '')
        call_context = request.POST.get('call_context', '')

        is_fraud, risk_score, reasons = analyze_call_fraud(phone_number, call_context, user=request.user)
        risk_level = get_risk_level_from_score(risk_score, is_fraud)

        CallFraudCheck.objects.create(
            user=request.user,
            phone_number=phone_number,
            call_context=call_context,
            is_fraud=is_fraud,
            risk_score=risk_score,
            risk_level=risk_level,
            detected_reasons="; ".join(reasons)
        )
        if is_fraud:
            messages.error(request, f"🚨 Fraud Call Warning! Call dialogue flagged with {risk_score}% risk. Alert sent to {request.user.email}.")
        else:
            messages.success(request, "✅ Call analysis complete: No scam markers detected.")

    return redirect('/?tab=call')


def submit_message(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.warning(request, "⚠️ Login required: Please sign in or register to inspect messages and SMS.")
            return redirect(f"{reverse('login')}?next={reverse('home')}?tab=message")

        sender_info = request.POST.get('sender_info', '')
        message_text = request.POST.get('message_text', '')

        is_fraud, risk_score, reasons = analyze_message_fraud(sender_info, message_text, user=request.user)
        risk_level = get_risk_level_from_score(risk_score, is_fraud)

        MessageFraudCheck.objects.create(
            user=request.user,
            sender_info=sender_info,
            message_text=message_text,
            is_fraud=is_fraud,
            risk_score=risk_score,
            risk_level=risk_level,
            detected_reasons="; ".join(reasons)
        )
        if is_fraud:
            messages.error(request, f"🚨 Scam SMS Detected! Message flagged with {risk_score}% risk. Alert sent to {request.user.email}.")
        else:
            messages.success(request, "✅ Message analysis complete: SMS text appears legitimate.")

    return redirect('/?tab=message')


# ---------------------------------------------------------------------------
# Update Action Risk Level (High / Medium / Low)
# ---------------------------------------------------------------------------

@login_required
def update_risk_level(request, log_type, item_id):
    """
    Allows user to switch the Action risk level (High, Medium, Low) for their scan history item.
    """
    model_map = {
        'transaction': TransactionCheck,
        'email': EmailFraudCheck,
        'call': CallFraudCheck,
        'message': MessageFraudCheck,
    }

    if log_type not in model_map:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({'success': False, 'error': 'Invalid log category'}, status=400)
        messages.error(request, "Invalid log category.")
        return redirect('home')

    model_class = model_map[log_type]
    if request.user.is_superuser:
        item = get_object_or_404(model_class, id=item_id)
    else:
        item = get_object_or_404(model_class, id=item_id, user=request.user)

    new_level = (request.POST.get('risk_level') or request.GET.get('level') or '').strip().upper()
    if new_level not in ['HIGH', 'MEDIUM', 'LOW']:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({'success': False, 'error': 'Invalid risk level. Choose High, Medium, or Low.'}, status=400)
        messages.error(request, "Invalid risk level.")
        return redirect(f"/?tab={log_type}")

    item.risk_level = new_level
    if new_level == 'HIGH':
        item.is_fraud = True
        if item.risk_score < 60:
            item.risk_score = 75
    elif new_level == 'MEDIUM':
        item.is_fraud = False
        if item.risk_score < 30 or item.risk_score >= 60:
            item.risk_score = 45
    elif new_level == 'LOW':
        item.is_fraud = False
        if item.risk_score >= 30:
            item.risk_score = 15
    item.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({
            'success': True,
            'log_type': log_type,
            'item_id': item_id,
            'risk_level': new_level,
            'risk_score': item.risk_score,
            'is_fraud': item.is_fraud,
            'message': f"Risk level updated to {new_level.capitalize()} successfully."
        })

    messages.success(request, f"Threat level updated to {new_level.capitalize()}.")
    return redirect(f"/?tab={log_type}")


# ---------------------------------------------------------------------------
# Delete Log Entry (Fallback / Admin Accessible)
# ---------------------------------------------------------------------------

@login_required
def delete_log(request, log_type, item_id):
    """
    Allows a user or admin to delete a scan history item.
    """
    model_map = {
        'transaction': (TransactionCheck, "Transaction Scan", lambda o: f"Email: {o.user_email}, Amount: ₹{o.amount}"),
        'email': (EmailFraudCheck, "Email Scan", lambda o: f"Sender: {o.sender_email}, Subject: {o.subject}"),
        'call': (CallFraudCheck, "Call Scan", lambda o: f"Phone: {o.phone_number}"),
        'message': (MessageFraudCheck, "SMS Scan", lambda o: f"Sender: {o.sender_info}"),
    }

    if log_type not in model_map:
        messages.error(request, "Invalid log category.")
        return redirect('home')

    model_class, type_label, info_func = model_map[log_type]

    try:
        if request.user.is_superuser:
            item = get_object_or_404(model_class, id=item_id)
        else:
            item = get_object_or_404(model_class, id=item_id, user=request.user)

        item_info = info_func(item)
        item.delete()

        try:
            send_log_deletion_email(request.user, type_label, item_info)
        except Exception as e:
            logger.warning(f"Error sending deletion confirmation email: {e}")

        messages.info(request, f"🗑️ {type_label} removed from your portal.")
    except Exception as e:
        logger.error(f"Error during log deletion: {e}")
        messages.error(request, f"Could not remove item: {e}")

    return redirect(f"/?tab={log_type}")



# Authentication views have been moved to dedicated 'account' app


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------

class FraudCheckAPIView(APIView):
    def post(self, request):
        email = request.data.get('email', '')
        amount_str = request.data.get('amount', 0)
        card_number = request.data.get('card_number', '')
        ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')
        user = request.user if request.user.is_authenticated else None

        is_fraud, risk_score, reasons, amount = analyze_transaction_fraud(email, amount_str, card_number, user=user)
        risk_level = get_risk_level_from_score(risk_score, is_fraud)

        record = TransactionCheck.objects.create(
            user=user,
            user_email=email,
            amount=amount,
            card_number=card_number,
            ip_address=ip_address,
            is_fraud=is_fraud,
            risk_score=risk_score,
            risk_level=risk_level
        )
        serializer = TransactionCheckSerializer(record)
        response_data = serializer.data
        response_data['reasons'] = reasons
        return Response(response_data, status=status.HTTP_201_CREATED)


class EmailFraudAPIView(APIView):
    def post(self, request):
        sender_email = request.data.get('sender_email', '')
        subject = request.data.get('subject', '')
        body_text = request.data.get('body_text', '')
        user = request.user if request.user.is_authenticated else None

        is_fraud, risk_score, reasons = analyze_email_fraud(sender_email, subject, body_text, user=user)
        risk_level = get_risk_level_from_score(risk_score, is_fraud)

        record = EmailFraudCheck.objects.create(
            user=user,
            sender_email=sender_email,
            subject=subject,
            body_text=body_text,
            is_fraud=is_fraud,
            risk_score=risk_score,
            risk_level=risk_level,
            detected_reasons="; ".join(reasons)
        )
        serializer = EmailFraudCheckSerializer(record)
        response_data = serializer.data
        response_data['reasons'] = reasons
        return Response(response_data, status=status.HTTP_201_CREATED)


class CallFraudAPIView(APIView):
    def post(self, request):
        phone_number = request.data.get('phone_number', '')
        call_context = request.data.get('call_context', '')
        user = request.user if request.user.is_authenticated else None

        is_fraud, risk_score, reasons = analyze_call_fraud(phone_number, call_context, user=user)
        risk_level = get_risk_level_from_score(risk_score, is_fraud)

        record = CallFraudCheck.objects.create(
            user=user,
            phone_number=phone_number,
            call_context=call_context,
            is_fraud=is_fraud,
            risk_score=risk_score,
            risk_level=risk_level,
            detected_reasons="; ".join(reasons)
        )
        serializer = CallFraudCheckSerializer(record)
        response_data = serializer.data
        response_data['reasons'] = reasons
        return Response(response_data, status=status.HTTP_201_CREATED)


class MessageFraudAPIView(APIView):
    def post(self, request):
        sender_info = request.data.get('sender_info', '')
        message_text = request.data.get('message_text', '')
        user = request.user if request.user.is_authenticated else None

        is_fraud, risk_score, reasons = analyze_message_fraud(sender_info, message_text, user=user)
        risk_level = get_risk_level_from_score(risk_score, is_fraud)

        record = MessageFraudCheck.objects.create(
            user=user,
            sender_info=sender_info,
            message_text=message_text,
            is_fraud=is_fraud,
            risk_score=risk_score,
            risk_level=risk_level,
            detected_reasons="; ".join(reasons)
        )
        serializer = MessageFraudCheckSerializer(record)
        response_data = serializer.data
        response_data['reasons'] = reasons
        return Response(response_data, status=status.HTTP_201_CREATED)


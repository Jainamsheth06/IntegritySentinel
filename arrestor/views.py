import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import FraudCase
from .serializers import FraudCaseSerializer

logger = logging.getLogger(__name__)


def arrestor_home(request):
    """
    Arrestor Case Management Portal:
    - Without login: Displays solved/completed case bulletin, live case tracking search, and anonymous report form.
    - With login: Displays user's cases, solved/completed status, priority management, and case registration.
    """
    query = request.GET.get('track_id', '').strip()
    tracked_case = None
    if query:
        tracked_case = FraudCase.objects.filter(case_id__iexact=query).first()

    # Public solved cases accessible to everyone (with and without login)
    solved_cases = FraudCase.objects.filter(Q(is_solved=True) | Q(status='COMPLETED')).order_by('-updated_at')[:10]

    user_cases = []
    if request.user.is_authenticated:
        if request.user.is_superuser:
            user_cases = FraudCase.objects.all().order_by('-created_at')[:20]
        else:
            user_cases = FraudCase.objects.filter(user=request.user).order_by('-created_at')
    else:
        # Public preview of recent cases for guests
        user_cases = FraudCase.objects.all().order_by('-created_at')[:5]

    total_cases = FraudCase.objects.count()
    completed_count = FraudCase.objects.filter(Q(is_solved=True) | Q(status='COMPLETED')).count()
    active_count = FraudCase.objects.filter(status__in=['PENDING', 'INVESTIGATING', 'ARREST_ISSUED']).count()

    return render(request, 'arrestor/index.html', {
        'user_cases': user_cases,
        'solved_cases': solved_cases,
        'tracked_case': tracked_case,
        'track_id': query,
        'total_cases': total_cases,
        'completed_count': completed_count,
        'active_count': active_count,
    })


def submit_case(request):
    """
    Submit a fraud incident for investigation / arrest.
    Works both with login and without login (guest filing).
    """
    if request.method == 'POST':
        victim_name = request.POST.get('victim_name', '').strip()
        victim_email = request.POST.get('victim_email', '').strip()
        victim_phone = request.POST.get('victim_phone', '').strip()
        fraud_category = request.POST.get('fraud_category', 'FINANCIAL')
        suspect_identity = request.POST.get('suspect_identity', '').strip()
        loss_amount_raw = request.POST.get('loss_amount', '0')
        priority = request.POST.get('priority', 'HIGH').upper()
        description = request.POST.get('description', '').strip()
        evidence_notes = request.POST.get('evidence_notes', '').strip()

        try:
            loss_amount = float(loss_amount_raw)
        except (ValueError, TypeError):
            loss_amount = 0.0

        if priority not in ['HIGH', 'MEDIUM', 'LOW']:
            priority = 'HIGH'

        case = FraudCase.objects.create(
            user=request.user if request.user.is_authenticated else None,
            victim_name=victim_name,
            victim_email=victim_email,
            victim_phone=victim_phone,
            fraud_category=fraud_category,
            suspect_identity=suspect_identity,
            loss_amount=loss_amount,
            priority=priority,
            description=description,
            evidence_notes=evidence_notes,
            status='PENDING',
        )

        messages.success(
            request,
            f"✅ Fraud Case registered successfully! Your Tracking ID is {case.case_id}. Keep this ID to check case status."
        )
        return redirect(f"/arrestor/?track_id={case.case_id}")

    return redirect('arrestor_home')


def track_case(request):
    """
    Quick status tracker endpoint (supports AJAX).
    Accessible with login and without login.
    """
    case_id = (request.GET.get('case_id') or request.POST.get('case_id') or '').strip()
    case = FraudCase.objects.filter(case_id__iexact=case_id).first()

    if not case:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Case ID not found.'}, status=404)
        messages.error(request, f"Case ID '{case_id}' was not found in the registry.")
        return redirect('arrestor_home')

    is_completed = case.is_solved or case.status == 'COMPLETED'
    status_label = "COMPLETED (Solved)" if is_completed else case.get_status_display()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'case_id': case.case_id,
            'victim_name': case.victim_name,
            'category': case.get_fraud_category_display(),
            'status': status_label,
            'is_completed': is_completed,
            'priority': case.priority,
            'loss_amount': str(case.loss_amount),
            'recovered_amount': str(case.recovered_amount),
            'assigned_officer': case.assigned_officer,
            'resolution_summary': case.resolution_summary or "Investigation in progress.",
            'created_at': case.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return redirect(f"/arrestor/?track_id={case.case_id}")


@login_required
def update_case_priority(request, case_id):
    """
    Allows user or admin to update the case Priority / Risk Level (High, Medium, Low) in the Action column.
    """
    if request.user.is_superuser:
        case = get_object_or_404(FraudCase, id=case_id)
    else:
        case = get_object_or_404(FraudCase, id=case_id, user=request.user)

    new_priority = (request.POST.get('priority') or request.GET.get('priority') or '').strip().upper()
    if new_priority not in ['HIGH', 'MEDIUM', 'LOW']:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Invalid priority level'}, status=400)
        messages.error(request, "Invalid priority level selected.")
        return redirect('arrestor_home')

    case.priority = new_priority
    case.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'case_id': case.case_id,
            'new_priority': new_priority,
            'message': f"Case {case.case_id} priority set to {new_priority}."
        })

    messages.success(request, f"Priority for {case.case_id} updated to {new_priority.capitalize()}.")
    return redirect('arrestor_home')


@login_required
def delete_case(request, case_id):
    """
    Fallback delete view (Primary deletion is recommended via Django Admin).
    """
    if request.user.is_superuser:
        case = get_object_or_404(FraudCase, id=case_id)
    else:
        case = get_object_or_404(FraudCase, id=case_id, user=request.user)

    case_id_str = case.case_id
    case.delete()
    messages.info(request, f"🗑️ Case {case_id_str} was deleted.")
    return redirect('arrestor_home')


# ---------------------------------------------------------------------------
# REST API Endpoints for Arrestor App
# ---------------------------------------------------------------------------

class CaseListCreateAPIView(APIView):
    def get(self, request):
        if request.user.is_authenticated:
            cases = FraudCase.objects.filter(user=request.user) if not request.user.is_superuser else FraudCase.objects.all()
        else:
            cases = FraudCase.objects.filter(Q(is_solved=True) | Q(status='COMPLETED'))[:20]

        serializer = FraudCaseSerializer(cases, many=True)
        return Response({'cases': serializer.data})

    def post(self, request):
        serializer = FraudCaseSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user if request.user.is_authenticated else None
            case = serializer.save(user=user)
            return Response(FraudCaseSerializer(case).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

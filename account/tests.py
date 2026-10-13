from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from account.models import UserProfile, UserRegistration
from arrestor.models import FraudCase
from detector.models import TransactionCheck, EmailFraudCheck, CallFraudCheck, MessageFraudCheck


class UnifiedAuthTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_detector_role(self):
        response = self.client.post(reverse('register'), {
            'first_name': 'Test',
            'last_name': 'Detector',
            'username': 'detector_user',
            'email': 'detector@test.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'detector',
        })
        # Should redirect to detector home '/'
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))
        user = User.objects.get(username='detector_user')
        self.assertEqual(user.profile.role, 'detector')

    def test_register_arrestor_role(self):
        response = self.client.post(reverse('register'), {
            'first_name': 'Officer',
            'last_name': 'Arrestor',
            'username': 'officer_user',
            'email': 'officer@test.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'arrestor',
        })
        # Should redirect to arrestor desk '/arrestor/'
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('arrestor_home'))
        user = User.objects.get(username='officer_user')
        self.assertEqual(user.profile.role, 'arrestor')

    def test_login_detector_redirect(self):
        user = User.objects.create_user('det_login', 'det@test.com', 'password123')
        UserProfile.objects.create(user=user, role='detector')

        response = self.client.post(reverse('login'), {
            'username': 'det_login',
            'password': 'password123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_login_arrestor_redirect(self):
        user = User.objects.create_user('arr_login', 'arr@test.com', 'password123')
        UserProfile.objects.create(user=user, role='arrestor')

        response = self.client.post(reverse('login'), {
            'username': 'arr_login',
            'password': 'password123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('arrestor_home'))

    def test_login_with_email(self):
        user = User.objects.create_user('email_user', 'user_email@test.com', 'password123')
        UserProfile.objects.create(user=user, role='detector')

        response = self.client.post(reverse('login'), {
            'username': 'user_email@test.com',
            'password': 'password123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_forgot_password_and_reset_flow(self):
        user = User.objects.create_user('reset_user', 'reset@test.com', 'oldpassword123')
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Check reset confirm GET
        confirm_url = reverse('reset_password_confirm', kwargs={'uidb64': uid, 'token': token})
        response = self.client.get(confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Set New Password')

        # Check reset confirm POST
        post_response = self.client.post(confirm_url, {
            'password': 'newpassword456',
            'confirm_password': 'newpassword456',
        })
        self.assertEqual(post_response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.check_password('newpassword456'))


class MediaAndPortalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('portal_user', 'portal@test.com', 'pass123')
        UserProfile.objects.create(user=self.user, role='detector')
        self.officer = User.objects.create_user('officer_boss', 'officer@police.gov', 'pass123')
        UserProfile.objects.create(user=self.officer, role='arrestor')

    def test_media_file_serves(self):
        response = self.client.get('/media/bg.jpg')
        self.assertEqual(response.status_code, 200)

    def test_detector_home_renders(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_update_action_risk_level(self):
        self.client.login(username='portal_user', password='pass123')
        item = TransactionCheck.objects.create(
            user=self.user,
            user_email='target@test.com',
            amount=5000,
            card_number='4111111111111111',
            risk_level='LOW',
            risk_score=10,
        )

        response = self.client.post(
            f"/update-risk-level/transaction/{item.id}/",
            {'risk_level': 'HIGH'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['risk_level'], 'HIGH')
        item.refresh_from_db()
        self.assertEqual(item.risk_level, 'HIGH')

    def test_arrestor_home_renders_and_update_priority(self):
        self.client.login(username='officer_boss', password='pass123')
        case = FraudCase.objects.create(
            case_id='TEST-ARR-101',
            victim_name='Alice Wonderland',
            victim_email='alice@example.com',
            victim_phone='9876543210',
            fraud_category='DIGITAL_ARREST',
            loss_amount=150000,
            priority='MEDIUM',
            status='INVESTIGATING',
            description='Impersonation extortion call reported',
            user=self.officer
        )

        # Home page contains case
        response = self.client.get(reverse('arrestor_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TEST-ARR-101')

        # Update priority via AJAX
        update_resp = self.client.post(
            f"/arrestor/update-priority/{case.id}/",
            {'priority': 'HIGH'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(update_resp.status_code, 200)
        data = update_resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_priority'], 'HIGH')
        case.refresh_from_db()
        self.assertEqual(case.priority, 'HIGH')

    def test_case_solved_displays_completed(self):
        solved_case = FraudCase.objects.create(
            case_id='SOLVED-999',
            victim_name='Bob Builder',
            victim_email='bob@example.com',
            victim_phone='9998887776',
            fraud_category='FINANCIAL',
            loss_amount=50000,
            priority='LOW',
            status='COMPLETED',
            description='Resolved card compromise',
            is_solved=True
        )

        # Public guest access
        response = self.client.get(reverse('arrestor_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'COMPLETED')
        self.assertContains(response, 'SOLVED-999')

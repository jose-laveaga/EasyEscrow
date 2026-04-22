from allauth.account import app_settings as account_settings
from allauth.account.adapter import get_adapter
from allauth.account.authentication import get_authentication_records
from allauth.account.forms import (
    AddEmailForm,
    ChangeEmailForm,
    ChangePasswordForm,
    ConfirmEmailVerificationCodeForm,
    ConfirmLoginCodeForm,
    ConfirmPasswordResetCodeForm,
    LoginForm,
    ReauthenticateForm,
    ResetPasswordForm,
    SetPasswordForm,
    SignupForm,
)
from allauth.account.internal import flows
from allauth.account.internal.flows import login_by_code, manage_email, password_reset_by_code
from allauth.account.internal.stagekit import get_pending_stage
from allauth.account.models import EmailAddress
from allauth.account.stages import LoginStageController
from allauth.core.exceptions import ImmediateHttpResponse, RateLimited, ReauthenticationRequired
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.urls import reverse
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from accounts.auth_serializers import (
    AuthUserSerializer,
    EmailActionSerializer,
    EmailVerificationActionSerializer,
    LoginCodeConfirmSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetCompleteSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    PasswordSetSerializer,
    ReauthenticateSerializer,
    SignupSerializer,
    EmptySerializer
)


def _extract_redirect_url(response: HttpResponse | None) -> str | None:
    if not response:
        return None
    return response.headers.get("Location") or getattr(response, "url", None)


def _raise_form_error(form) -> None:
    raise DRFValidationError(form.errors)


def _raise_django_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise DRFValidationError(exc.message_dict)
    raise DRFValidationError(exc.messages)


def _serialize_user(user):
    if not user or not user.is_authenticated:
        return None
    return AuthUserSerializer(user).data


def _serialize_email_address(address: EmailAddress) -> dict:
    return {
        "email": address.email,
        "verified": address.verified,
        "primary": address.primary,
    }


def _email_verification_process(request):
    if not account_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED:
        return None
    return flows.email_verification_by_code.EmailVerificationProcess.resume(request)


def _password_reset_process(request):
    if not account_settings.PASSWORD_RESET_BY_CODE_ENABLED:
        return None
    return password_reset_by_code.PasswordResetVerificationProcess.resume(request)


def _login_code_process(request):
    stage = LoginStageController.enter(request, "login_by_code")
    if not stage:
        return None, None
    process = login_by_code.LoginCodeVerificationProcess.resume(stage)
    return stage, process


def _build_pending_step(request):
    password_reset_process = _password_reset_process(request)
    if password_reset_process:
        return {
            "id": "password_reset",
            "url": reverse(
                "account_complete_password_reset"
                if password_reset_process.state.get("code_confirmed")
                else "account_confirm_password_reset_code"
            ),
            "email": password_reset_process.state.get("email"),
            "code_confirmed": bool(password_reset_process.state.get("code_confirmed")),
        }

    email_process = _email_verification_process(request)
    if email_process:
        return {
            "id": "email_verification",
            "url": reverse("account_email_verification_sent"),
            "email": email_process.state.get("email"),
            "can_resend": email_process.can_resend,
            "can_change": email_process.can_change,
        }

    stage = get_pending_stage(request)
    if stage:
        pending = {
            "id": stage.key,
            "url": reverse(stage.urlname) if stage.urlname else None,
        }
        if stage.key == "login_by_code":
            _, process = _login_code_process(request)
            if process:
                pending["email"] = process.state.get("email")
                pending["phone"] = process.state.get("phone")
                pending["can_resend"] = process.can_resend
        return pending

    return None


def _build_session_payload(request) -> dict:
    payload = {
        "is_authenticated": bool(request.user and request.user.is_authenticated),
        "user": _serialize_user(request.user),
    }
    if request.user.is_authenticated:
        payload["authentication_methods"] = get_authentication_records(request)
    pending = _build_pending_step(request)
    if pending:
        payload["pending"] = pending
    return payload


def _email_state_payload(request) -> dict:
    assert request.user.is_authenticated  # nosec
    manage_email.sync_user_email_address(request.user)
    addresses = manage_email.list_email_addresses(request, request.user)
    pending = _build_pending_step(request)
    return {
        "emails": [_serialize_email_address(address) for address in addresses],
        "pending_verification": pending if pending and pending["id"] == "email_verification" else None,
    }


def _get_email_address_for_user(user, email: str) -> EmailAddress | None:
    email = email.strip().lower()
    return EmailAddress.objects.filter(user=user, email=email).first()


class AllauthAPIView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def build_response(
        self,
        *,
        detail: str,
        status_code: int = status.HTTP_200_OK,
        redirect_to: str | None = None,
        extra: dict | None = None,
    ) -> Response:
        payload = {
            "detail": detail,
            "redirect_to": redirect_to,
            "session": _build_session_payload(self.request),
        }
        if extra:
            payload.update(extra)
        return Response(payload, status=status_code)

    def handle_allauth_exception(self, exc):
        if isinstance(exc, DRFValidationError):
            raise exc
        if isinstance(exc, DjangoValidationError):
            _raise_django_validation_error(exc)
        if isinstance(exc, ReauthenticationRequired):
            return self.build_response(
                detail="Reauthentication required.",
                status_code=status.HTTP_401_UNAUTHORIZED,
                redirect_to=reverse("account_reauthenticate"),
            )
        if isinstance(exc, RateLimited):
            return self.build_response(
                detail="Too many requests. Try again later.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        raise exc


class LoginAPIView(AllauthAPIView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return self.build_response(
                detail="An authenticated session already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = LoginForm(data=serializer.validated_data, request=request)
        if not form.is_valid():
            _raise_form_error(form)

        try:
            response = form.login(request)
        except Exception as exc:  # pragma: no cover - centralized handling
            handled = self.handle_allauth_exception(exc)
            if handled is not None:
                return handled
            raise

        redirect_to = _extract_redirect_url(response)
        detail = "Login successful." if request.user.is_authenticated else "Additional authentication is required."
        return self.build_response(detail=detail, redirect_to=redirect_to)




class LogoutAPIView(AllauthAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmptySerializer

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            get_adapter(request).logout(request)
            detail = "Logged out successfully."
        else:
            detail = "No active session."
        return self.build_response(
            detail=detail,
            redirect_to=get_adapter(request).get_logout_redirect_url(request),
        )


class SignupAPIView(AllauthAPIView):
    serializer_class = SignupSerializer

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return self.build_response(
                detail="An authenticated session already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        if not get_adapter(request).is_open_for_signup(request):
            return self.build_response(
                detail="Signups are currently closed.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = SignupForm(data=serializer.validated_data)
        if not form.is_valid():
            _raise_form_error(form)

        try:
            user, response = form.try_save(request)
            if not response:
                response = flows.signup.complete_signup(
                    request,
                    user=user,
                    by_passkey=form.by_passkey,
                )
        except ImmediateHttpResponse as exc:
            response = exc.response
        except Exception as exc:  # pragma: no cover - centralized handling
            handled = self.handle_allauth_exception(exc)
            if handled is not None:
                return handled
            raise

        redirect_to = _extract_redirect_url(response)
        detail = "Signup completed." if request.user.is_authenticated else "Signup accepted. Complete the remaining verification step."
        return self.build_response(
            detail=detail,
            status_code=status.HTTP_201_CREATED,
            redirect_to=redirect_to,
        )


class ReauthenticateAPIView(AllauthAPIView):
    serializer_class = ReauthenticateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = ReauthenticateForm(data=serializer.validated_data, user=request.user)
        if not form.is_valid():
            _raise_form_error(form)

        try:
            flows.reauthentication.reauthenticate_by_password(request)
            response = flows.reauthentication.resume_request(request)
        except Exception as exc:  # pragma: no cover - centralized handling
            handled = self.handle_allauth_exception(exc)
            if handled is not None:
                return handled
            raise

        return self.build_response(
            detail="Reauthentication successful.",
            redirect_to=_extract_redirect_url(response),
        )


class EmailAPIView(AllauthAPIView):
    serializer_class = EmailActionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return self.build_response(
            detail="Email addresses retrieved.",
            extra=_email_state_payload(request),
        )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        email = serializer.validated_data["email"]

        try:
            redirect_to = None
            if action == "add":
                form = AddEmailForm(data={"email": email}, user=request.user)
                if not form.is_valid():
                    _raise_form_error(form)
                manage_email.add_email(request, form)
                if account_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED:
                    redirect_to = reverse("account_email_verification_sent")
                detail = "Verification sent to the new email address."
            else:
                email_address = _get_email_address_for_user(request.user, email)
                if not email_address:
                    raise DRFValidationError({"email": ["Email address not found on this account."]})

                if action == "send":
                    did_send = flows.email_verification.send_verification_email_to_address(
                        request, email_address
                    )
                    if not did_send:
                        return self.build_response(
                            detail="Verification email could not be sent.",
                            status_code=status.HTTP_403_FORBIDDEN,
                            extra=_email_state_payload(request),
                        )
                    redirect_to = reverse("account_email_verification_sent")
                    detail = "Verification email sent."
                elif action == "remove":
                    if not manage_email.delete_email(request, email_address):
                        raise DRFValidationError(
                            {"email": ["This email address cannot be removed."]}
                        )
                    detail = "Email address removed."
                else:
                    if not manage_email.mark_as_primary(request, email_address):
                        raise DRFValidationError(
                            {"email": ["This email address cannot be made primary."]}
                        )
                    detail = "Primary email updated."
        except Exception as exc:  # pragma: no cover - centralized handling
            handled = self.handle_allauth_exception(exc)
            if handled is not None:
                return handled
            raise

        return self.build_response(
            detail=detail,
            redirect_to=redirect_to,
            extra=_email_state_payload(request),
        )


class ConfirmEmailAPIView(AllauthAPIView):
    serializer_class = EmailVerificationActionSerializer

    def _get_process(self, request):
        process = _email_verification_process(request)
        if not process:
            return None
        stage = LoginStageController.enter(request, "verify_email")
        return process, stage

    def get(self, request, *args, **kwargs):
        found = self._get_process(request)
        if not found:
            return self.build_response(
                detail="No email verification is pending.",
                status_code=status.HTTP_409_CONFLICT,
            )
        process, stage = found
        return self.build_response(
            detail="Email verification is pending.",
            extra={
                "verification": {
                    "email": process.state.get("email"),
                    "can_resend": process.can_resend,
                    "can_change": process.can_change,
                    "is_authenticating": bool(stage),
                }
            },
        )

    def post(self, request, *args, **kwargs):
        found = self._get_process(request)
        if not found:
            return self.build_response(
                detail="No email verification is pending.",
                status_code=status.HTTP_409_CONFLICT,
            )
        process, stage = found

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        try:
            if action == "resend":
                process.resend()
                return self.build_response(
                    detail="Verification code resent.",
                    redirect_to=reverse("account_email_verification_sent"),
                    extra={
                        "verification": {
                            "email": process.state.get("email"),
                            "can_resend": process.can_resend,
                            "can_change": process.can_change,
                            "is_authenticating": bool(stage),
                        }
                    },
                )

            if action == "change":
                email = serializer.validated_data["email"]
                form = ChangeEmailForm(
                    data={"email": email},
                    email=process.state.get("email"),
                )
                if not form.is_valid():
                    _raise_form_error(form)
                process.change_to(form.cleaned_data["email"], form.account_already_exists)
                return self.build_response(
                    detail="Verification email updated.",
                    redirect_to=reverse("account_email_verification_sent"),
                    extra={
                        "verification": {
                            "email": process.state.get("email"),
                            "can_resend": process.can_resend,
                            "can_change": process.can_change,
                            "is_authenticating": bool(stage),
                        }
                    },
                )

            form = ConfirmEmailVerificationCodeForm(
                data={"code": serializer.validated_data["code"]},
                code=process.code,
                user=process.user,
                email=process.email,
            )
            if not form.is_valid():
                attempts_left = process.record_invalid_attempt()
                if not attempts_left:
                    return self.build_response(
                        detail="Too many invalid verification attempts.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                        redirect_to=reverse("account_login"),
                    )
                _raise_form_error(form)

            email_address = process.finish()
            if stage:
                response = stage.exit() if email_address else stage.abort()
                redirect_to = _extract_redirect_url(response)
            else:
                redirect_to = (
                    get_adapter(request).get_email_verification_redirect_url(email_address)
                    if email_address
                    else reverse("account_email")
                )
            return self.build_response(
                detail="Email verified successfully.",
                redirect_to=redirect_to,
            )
        except Exception as exc:  # pragma: no cover - centralized handling
            handled = self.handle_allauth_exception(exc)
            if handled is not None:
                return handled
            raise


class PasswordChangeAPIView(AllauthAPIView):
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not request.user.has_usable_password():
            return self.build_response(
                detail="Set a password before attempting to change it.",
                status_code=status.HTTP_409_CONFLICT,
                redirect_to=reverse("account_set_password"),
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = ChangePasswordForm(data=serializer.validated_data, user=request.user)
        if not form.is_valid():
            _raise_form_error(form)

        form.save()
        flows.password_change.finalize_password_change(request, request.user)
        return self.build_response(detail="Password changed successfully.")


class PasswordSetAPIView(AllauthAPIView):
    serializer_class = PasswordSetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.has_usable_password():
            return self.build_response(
                detail="A password is already set for this account.",
                status_code=status.HTTP_409_CONFLICT,
                redirect_to=reverse("account_change_password"),
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = SetPasswordForm(data=serializer.validated_data, user=request.user)
        if not form.is_valid():
            _raise_form_error(form)

        form.save()
        flows.password_change.finalize_password_set(request, request.user)
        return self.build_response(detail="Password set successfully.")


class PasswordResetAPIView(AllauthAPIView):
    serializer_class = PasswordResetSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = ResetPasswordForm(data=serializer.validated_data)
        if not form.is_valid():
            _raise_form_error(form)

        try:
            form.save(request)
        except Exception as exc:  # pragma: no cover - centralized handling
            handled = self.handle_allauth_exception(exc)
            if handled is not None:
                return handled
            raise

        redirect_to = reverse(
            "account_confirm_password_reset_code"
            if account_settings.PASSWORD_RESET_BY_CODE_ENABLED
            else "account_reset_password_done"
        )
        return self.build_response(
            detail="Password reset instructions have been issued if the account exists.",
            redirect_to=redirect_to,
        )


class ConfirmPasswordResetCodeAPIView(AllauthAPIView):
    serializer_class = PasswordResetConfirmSerializer

    def get(self, request, *args, **kwargs):
        process = _password_reset_process(request)
        if not process:
            return self.build_response(
                detail="No password reset is pending.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return self.build_response(
            detail="Password reset code confirmation is pending.",
            extra={
                "password_reset": {
                    "email": process.state.get("email"),
                    "code_confirmed": bool(process.state.get("code_confirmed")),
                }
            },
        )

    def post(self, request, *args, **kwargs):
        process = _password_reset_process(request)
        if not process:
            return self.build_response(
                detail="No password reset is pending.",
                status_code=status.HTTP_409_CONFLICT,
            )
        if process.state.get("code_confirmed"):
            return self.build_response(
                detail="Password reset code already confirmed.",
                redirect_to=reverse("account_complete_password_reset"),
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = ConfirmPasswordResetCodeForm(
            data={"code": serializer.validated_data["code"]},
            code=process.code,
        )
        if not form.is_valid():
            attempts_left = process.record_invalid_attempt()
            if not attempts_left:
                return self.build_response(
                    detail="Too many invalid password reset attempts.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    redirect_to=reverse("account_login"),
                )
            _raise_form_error(form)

        process.confirm_code()
        return self.build_response(
            detail="Password reset code confirmed.",
            redirect_to=reverse("account_complete_password_reset"),
        )


class CompletePasswordResetAPIView(AllauthAPIView):
    serializer_class = PasswordResetCompleteSerializer

    def get(self, request, *args, **kwargs):
        process = _password_reset_process(request)
        if not process:
            return self.build_response(
                detail="No password reset is pending.",
                status_code=status.HTTP_409_CONFLICT,
            )
        if not process.state.get("code_confirmed"):
            return self.build_response(
                detail="Password reset code must be confirmed first.",
                status_code=status.HTTP_409_CONFLICT,
                redirect_to=reverse("account_confirm_password_reset_code"),
            )
        return self.build_response(
            detail="Password reset can be completed.",
            extra={
                "password_reset": {
                    "email": process.state.get("email"),
                    "code_confirmed": True,
                }
            },
        )

    def post(self, request, *args, **kwargs):
        process = _password_reset_process(request)
        if not process:
            return self.build_response(
                detail="No password reset is pending.",
                status_code=status.HTTP_409_CONFLICT,
            )
        if not process.state.get("code_confirmed"):
            return self.build_response(
                detail="Password reset code must be confirmed first.",
                status_code=status.HTTP_409_CONFLICT,
                redirect_to=reverse("account_confirm_password_reset_code"),
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = SetPasswordForm(data=serializer.validated_data, user=process.user)
        if not form.is_valid():
            _raise_form_error(form)

        form.save()
        response = process.finish()
        return self.build_response(
            detail="Password has been reset successfully.",
            redirect_to=_extract_redirect_url(response)
            or reverse("account_password_reset_completed"),
        )


class PasswordResetDoneAPIView(AllauthAPIView):
    def get(self, request, *args, **kwargs):
        return self.build_response(detail="Password reset is complete.")


class AccountInactiveAPIView(AllauthAPIView):
    def get(self, request, *args, **kwargs):
        return self.build_response(
            detail="This account is inactive.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConfirmLoginCodeAPIView(AllauthAPIView):
    serializer_class = LoginCodeConfirmSerializer

    def get(self, request, *args, **kwargs):
        stage, process = _login_code_process(request)
        if not stage or not process:
            return self.build_response(
                detail="No login code confirmation is pending.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return self.build_response(
            detail="Login code confirmation is pending.",
            extra={
                "login_code": {
                    "email": process.state.get("email"),
                    "phone": process.state.get("phone"),
                    "can_resend": process.can_resend,
                }
            },
        )

    def post(self, request, *args, **kwargs):
        stage, process = _login_code_process(request)
        if not stage or not process:
            return self.build_response(
                detail="No login code confirmation is pending.",
                status_code=status.HTTP_409_CONFLICT,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = ConfirmLoginCodeForm(
            data={"code": serializer.validated_data["code"]},
            code=process.code,
        )
        if not form.is_valid():
            attempts_left = process.record_invalid_attempt()
            if not attempts_left:
                return self.build_response(
                    detail="Too many invalid login code attempts.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    redirect_to=reverse("account_login"),
                )
            _raise_form_error(form)

        response = process.finish(redirect_url=None)
        return self.build_response(
            detail="Login code confirmed.",
            redirect_to=_extract_redirect_url(response),
        )

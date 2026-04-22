from rest_framework import serializers

from accounts.models import User

class EmptySerializer(serializers.Serializer):
    pass

class AuthUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "is_staff",
        ]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    login = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    remember = serializers.BooleanField(required=False)


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password1 = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)


class ReauthenticateSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class EmailActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["add", "send", "remove", "primary"])
    email = serializers.EmailField(required=False)

    def validate(self, attrs):
        action = attrs["action"]
        email = attrs.get("email")
        if action in {"add", "send", "remove", "primary"} and not email:
            raise serializers.ValidationError({"email": "This field is required."})
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    oldpassword = serializers.CharField(write_only=True, trim_whitespace=False)
    password1 = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordSetSerializer(serializers.Serializer):
    password1 = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(trim_whitespace=True)


class PasswordResetCompleteSerializer(serializers.Serializer):
    password1 = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)


class EmailVerificationActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["verify", "change", "resend"])
    code = serializers.CharField(required=False, trim_whitespace=True)
    email = serializers.EmailField(required=False)

    def validate(self, attrs):
        action = attrs["action"]
        if action == "verify" and not attrs.get("code"):
            raise serializers.ValidationError({"code": "This field is required."})
        if action == "change" and not attrs.get("email"):
            raise serializers.ValidationError({"email": "This field is required."})
        return attrs


class LoginCodeConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(trim_whitespace=True)

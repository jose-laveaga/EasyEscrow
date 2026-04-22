from django import forms

from accounts.validators import name_place_validator


class EscrowSignupForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        required=True,
        validators=[name_place_validator],
    )
    middle_name = forms.CharField(
        max_length=150,
        required=False,
        validators=[name_place_validator],
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        validators=[name_place_validator],
    )

    field_order = [
        "email",
        "first_name",
        "middle_name",
        "last_name",
        "password1",
        "password2",
    ]

    def signup(self, request, user) -> None:
        user.middle_name = self.cleaned_data.get("middle_name", "").strip()
        user.save(update_fields=["middle_name", "updated_at"])

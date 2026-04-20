from django.core.validators import RegexValidator

rfc_validator = RegexValidator(
    regex=r"^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$",
    message="Enter a valid Mexican RFC.",
)

phone_validator = RegexValidator(
    regex=r"^\+52\d{10}$",
    message="Enter a valid Mexican phone number in the format +52XXXXXXXXXX.",
)

name_place_validator = RegexValidator(
    regex=r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'.\- ]{2,100}$",
    message="This field contains invalid characters.",
)

curp_validator = RegexValidator(
    regex=r"^[A-Z][AEIOUX][A-Z]{2}\d{2}"
    r"(0[1-9]|1[0-2])"
    r"(0[1-9]|[12]\d|3[01])"
    r"[HM]"
    r"(AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)"
    r"[B-DF-HJ-NP-TV-Z]{3}[A-Z\d]\d$",
    message="CURP must be a valid Mexican CURP format.",
)

postal_code_validator = RegexValidator(
    regex=r"^\d{5}$",
    message="Enter a valid Mexican postal code.",
)
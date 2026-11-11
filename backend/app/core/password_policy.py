PASSWORD_MIN_LENGTH = 8


class PasswordPolicyError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_password(
    password: str,
    confirmation: str,
    email: str,
) -> None:
    if password != confirmation:
        raise PasswordPolicyError("PASSWORD_MISMATCH", "Passwords do not match")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise PasswordPolicyError("PASSWORD_TOO_SHORT", f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if password.casefold() == email.casefold():
        raise PasswordPolicyError("PASSWORD_EQUALS_EMAIL", "Password cannot be the same as email")
    if not any(character.islower() for character in password):
        raise PasswordPolicyError("PASSWORD_NEEDS_LOWER", "Password must include a lowercase letter")
    if not any(character.isupper() for character in password):
        raise PasswordPolicyError("PASSWORD_NEEDS_UPPER", "Password must include an uppercase letter")
    if not any(character.isdigit() for character in password):
        raise PasswordPolicyError("PASSWORD_NEEDS_DIGIT", "Password must include a number")
    if not any(not character.isalnum() and not character.isspace() for character in password):
        raise PasswordPolicyError("PASSWORD_NEEDS_SYMBOL", "Password must include a special character")

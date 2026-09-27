def validate_password(
    password: str,
    confirmation: str,
    email: str,
    minimum_length: int,
) -> None:
    if password != confirmation:
        raise ValueError("Passwords do not match")
    if len(password) < minimum_length:
        raise ValueError(f"Password must be at least {minimum_length} characters")
    if password.casefold() == email.casefold():
        raise ValueError("Password cannot be the same as email")
    if not any(character.islower() for character in password):
        raise ValueError("Password must include a lowercase letter")
    if not any(character.isupper() for character in password):
        raise ValueError("Password must include an uppercase letter")
    if not any(character.isdigit() for character in password):
        raise ValueError("Password must include a number")
    if not any(not character.isalnum() and not character.isspace() for character in password):
        raise ValueError("Password must include a special character")

def password_policy_error(password):
    message = (
        "Password must be at least 8 characters and include an uppercase letter, "
        "a lowercase letter, and a special character."
    )

    if not isinstance(password, str) or len(password) < 8:
        return message
    if not any(char.isupper() for char in password):
        return message
    if not any(char.islower() for char in password):
        return message
    if not any(not char.isalnum() and not char.isspace() for char in password):
        return message

    return None

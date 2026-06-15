import re

def is_password_strong(password):
    if len(password) < 8:
        return False
    if not re.search(r"\d", password): # Pelo menos 1 número
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): # Pelo menos 1 especial
        return False
    return True
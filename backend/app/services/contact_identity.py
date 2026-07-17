from email.utils import parseaddr


def normalize_email_identity(value: str) -> str:
    """Normalize customer email identities without hiding the original channel type.

    This reduces accidental duplicates from casing and common plus-address aliases.
    Gmail/Googlemail also ignore dots in the local part, so we normalize those too.
    """

    _name, parsed = parseaddr(str(value or ""))
    email = parsed.strip().lower()
    if "@" not in email:
        return ""
    local, domain = email.rsplit("@", 1)
    if "+" in local:
        local = local.split("+", 1)[0]
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def normalize_phone_identity(value: str) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())

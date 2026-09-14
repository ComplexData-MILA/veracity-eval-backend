import re
from urllib.parse import urlsplit

MAX_DOMAINS = 10

DOMAIN_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def normalize_preferred_domains(
    domains: list[str] | None,
) -> list[str]:
    if not domains:
        return []

    if len(domains) > MAX_DOMAINS:
        raise ValueError(f"Select at most {MAX_DOMAINS} domains.")

    normalized = []

    for entry in domains:
        value = entry.strip()

        if not value or any(char.isspace() for char in value):
            raise ValueError("Enter a valid domain without spaces.")

        # Accept either a domain or a website URL.
        candidate = value if "://" in value else f"https://{value}"

        try:
            parsed = urlsplit(candidate)
            hostname = parsed.hostname

            if (
                parsed.scheme not in {"http", "https"}
                or not hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port is not None
            ):
                raise ValueError("Invalid domain.")

            domain = hostname.encode("idna").decode("ascii").lower()
        except (ValueError, UnicodeError):
            raise ValueError("Enter a valid domain or website URL.") from None

        if domain.startswith("www."):
            domain = domain[4:]

        labels = domain.split(".")

        if (
            len(domain) > 253
            or len(labels) < 2
            or not all(DOMAIN_LABEL.fullmatch(label) for label in labels)
            or labels[-1].isdigit()
        ):
            raise ValueError("Enter a valid domain, such as nih.gov.")

        if domain not in normalized:
            normalized.append(domain)

    return normalized

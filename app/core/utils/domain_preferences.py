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


def build_domain_query(
    query: str,
    domains: list[str] | None,
) -> str:
    if not domains:
        return query

    restrictions = " OR ".join(f"site:{domain}" for domain in domains)
    return f"({query}) ({restrictions})"


def matches_preferred_domain(
    url: str,
    domains: list[str] | None,
) -> bool:
    if not domains:
        return True

    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname = hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except (ValueError, UnicodeError):
        return False

    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)

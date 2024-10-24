from urllib.parse import urlparse
import tld
import re


def normalize_domain_name(url: str) -> str:
    """
    Normalize a domain name or URL to a consistent format.

    Examples:
        >>> normalize_domain_name("https://www.example.com/path")
        'example.com'
        >>> normalize_domain_name("subdomain.example.co.uk")
        'example.co.uk'
        >>> normalize_domain_name("www.EXAMPLE.com")
        'example.com'
    """
    try:
        # Check if it's a full URL
        if "//" not in url:
            url = f"http://{url}"

        # Parse the URL
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path

        # Remove port number if present
        domain = domain.split(":")[0]

        # Remove www. if present
        domain = re.sub(r"^www\.", "", domain)

        # Extract the registered domain using tld
        try:
            res = tld.get_tld(domain, as_object=True, fix_protocol=True)
            domain = res.fld
        except tld.exceptions.TldDomainNotFound:
            # If not a valid TLD, just clean and return
            pass

        # Convert to lowercase
        return domain.lower().strip()
    except Exception:
        # If anything goes wrong, return cleaned input
        return url.lower().strip()


def extract_urls_from_text(text: str) -> list[str]:
    """
    Extract URLs from text content.

    Examples:
        >>> text = "Check this link https://example.com and www.test.com"
        >>> extract_urls_from_text(text)
        ['https://example.com', 'www.test.com']
    """
    # URL pattern matching both http(s) and www formats
    url_pattern = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"
    www_pattern = r"www\.(?:[-\w.]|(?:%[\da-fA-F]{2}))+"

    # Find all matches
    urls = re.findall(url_pattern, text, re.IGNORECASE)
    www_urls = re.findall(www_pattern, text, re.IGNORECASE)

    # Combine and normalize
    return [normalize_domain_name(url) for url in urls + www_urls]


def is_valid_domain(domain: str) -> bool:
    """
    Check if a string is a valid domain name.

    Examples:
        >>> is_valid_domain("example.com")
        True
        >>> is_valid_domain("not@valid")
        False
    """
    try:
        # Clean the domain first
        domain = normalize_domain_name(domain)

        # Check basic domain pattern
        pattern = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$"
        if not re.match(pattern, domain):
            return False

        # Verify TLD exists
        return bool(tld.get_tld(f"http://{domain}", fail_silently=True))
    except Exception:
        return False

from uuid import UUID
from datetime import datetime


class Domain:
    def __init__(
        self,
        id: UUID,
        domain_name: str,
        credibility_score: float,
        is_reliable: bool,
        description: str = None,
        created_at: datetime = None,
        updated_at: datetime = None,
    ):
        self.id = id
        self.domain_name = domain_name
        self.credibility_score = credibility_score
        self.is_reliable = is_reliable
        self.description = description
        self.created_at = created_at
        self.updated_at = updated_at

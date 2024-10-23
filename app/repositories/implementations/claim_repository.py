from app.models.domain.claim import Claim
from app.models.database.models import ClaimModel
from app.repositories.base import BaseRepository


class ClaimRepository(BaseRepository[ClaimModel, Claim]):
    def __init__(self, session):
        super().__init__(session, ClaimModel)

    def _to_model(self, claim: Claim) -> ClaimModel:
        return ClaimModel(
            id=claim.id,
            user_id=claim.user_id,
            claim_text=claim.claim_text,
            context=claim.context,
            created_at=claim.created_at,
        )

    def _to_domain(self, model: ClaimModel) -> Claim:
        return Claim(
            id=model.id,
            user_id=model.user_id,
            claim_text=model.claim_text,
            context=model.context,
            created_at=model.created_at,
        )

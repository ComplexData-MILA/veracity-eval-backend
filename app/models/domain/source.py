from uuid import UUID


class Source:
    def __init__(self, id: UUID, analysis_id: UUID, url: str, title: str, snippet: str, credibility_score: float):
        self.id = id
        self.analysis_id = analysis_id
        self.url = url
        self.title = title
        self.snippet = snippet
        self.credibility_score = credibility_score

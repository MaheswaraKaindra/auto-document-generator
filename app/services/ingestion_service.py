from app.domain.models import SourceType, Workspace
from app.ingestion.provider_factory import get_provider


class IngestionService:
    def __init__(self, provider_lookup=get_provider):
        self._provider_lookup = provider_lookup

    def ingest(self, source_type: SourceType, requests: list) -> list[Workspace]:
        provider = self._provider_lookup(source_type)
        return [provider.fetch(request) for request in requests]

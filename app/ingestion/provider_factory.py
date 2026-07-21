from app.domain.models import SourceType
from app.domain.ports import SourceProvider
from app.ingestion.providers.github_provider import GithubSourceProvider
from app.ingestion.providers.zip_provider import ZipUploadProvider

_PROVIDER_CLASSES: dict[SourceType, type[SourceProvider]] = {
    SourceType.GITHUB: GithubSourceProvider,
    SourceType.ZIP_UPLOAD: ZipUploadProvider,
}

_instances: dict[SourceType, SourceProvider] = {}


def get_provider(source_type: SourceType) -> SourceProvider:
    if source_type not in _instances:
        provider_cls = _PROVIDER_CLASSES[source_type]
        _instances[source_type] = provider_cls()
    return _instances[source_type]

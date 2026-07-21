from abc import ABC, abstractmethod

from app.domain.models import Workspace


class SourceProvider(ABC):
    @abstractmethod
    def fetch(self, request) -> Workspace:
        ...

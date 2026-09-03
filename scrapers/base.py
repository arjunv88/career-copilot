from abc import ABC, abstractmethod

from scrapers.models import (
    DiscoveredJob,
)


class JobSource(ABC):

    @abstractmethod
    def search_jobs(
        self,
    ) -> list[DiscoveredJob]:

        pass
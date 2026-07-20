"""Provider registry for Search Hub."""

from providers.base import ProviderConnector
from providers.firecrawl import FirecrawlConnector
from providers.tavily import TavilyConnector

PROVIDER_REGISTRY: dict[str, type[ProviderConnector]] = {
    "firecrawl": FirecrawlConnector,
    "tavily": TavilyConnector,
}

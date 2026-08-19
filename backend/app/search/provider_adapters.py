from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from backend.app.citations.domain import ParsedCitation
from backend.app.search.execution_domain import SearchProvider, SearchProviderResult
from backend.app.search.provider_domain import (
    ProviderAttemptSnapshot,
    ProviderFailureClass,
    SearchProviderCapability,
    SearchProviderError,
)
from backend.app.search.provider_http import (
    HttpxSearchHttpTransport,
    ProviderHttpClient,
    SearchHttpResponse,
    SearchHttpTransport,
    build_polite_user_agent,
)


@dataclass(frozen=True, slots=True)
class ProviderRuntimeConfig:
    user_agent: str = "ResearchTool/0.1"
    contact_email: str | None = None
    timeout_seconds: float = 30.0
    max_response_bytes: int = 2_000_000
    max_attempts: int = 3
    backoff_base_seconds: float = 0.25
    backoff_cap_seconds: float = 4.0
    min_interval_seconds: float = 0.1
    max_aggregate_raw_bytes: int = 10_000_000
    pubmed_api_key: str | None = None

    @property
    def polite_user_agent(self) -> str:
        return build_polite_user_agent(self.user_agent, self.contact_email)


OPENALEX_CAPABILITY = SearchProviderCapability(
    key="openalex",
    display_name="OpenAlex",
    version="openalex-http-1",
    base_url="https://api.openalex.org/works",
    allowed_hosts=frozenset({"api.openalex.org"}),
    supports_pagination=True,
    max_page_size=200,
    requires_api_key=False,
    default_media_type="application/json",
)

PUBMED_CAPABILITY = SearchProviderCapability(
    key="pubmed",
    display_name="PubMed",
    version="pubmed-eutils-http-1",
    base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    allowed_hosts=frozenset({"eutils.ncbi.nlm.nih.gov"}),
    supports_pagination=True,
    max_page_size=200,
    requires_api_key=False,
    default_media_type="application/xml",
)

EUROPE_PMC_CAPABILITY = SearchProviderCapability(
    key="europe-pmc",
    display_name="Europe PMC",
    version="europe-pmc-http-1",
    base_url="https://www.ebi.ac.uk/europepmc/webservices/rest/search",
    allowed_hosts=frozenset({"www.ebi.ac.uk"}),
    supports_pagination=True,
    max_page_size=1000,
    requires_api_key=False,
    default_media_type="application/json",
)

FIXTURE_CAPABILITY = SearchProviderCapability(
    key="fixture",
    display_name="Deterministic fixture",
    version="fixture-search-1",
    base_url="fixture://offline",
    allowed_hosts=frozenset(),
    supports_pagination=True,
    max_page_size=200,
    requires_api_key=False,
    default_media_type="application/json",
)


def _page_limits(
    capability: SearchProviderCapability, max_pages: int, page_size: int
) -> tuple[int, int]:
    if max_pages < 1 or max_pages > 100:
        raise ValueError("provider max_pages must be between 1 and 100")
    if page_size < 1 or page_size > capability.max_page_size:
        raise ValueError(f"provider page_size must be between 1 and {capability.max_page_size}")
    return max_pages, page_size


def _client(
    capability: SearchProviderCapability,
    config: ProviderRuntimeConfig,
    transport: SearchHttpTransport | None,
    *,
    sensitive_param_keys: frozenset[str] = frozenset(),
) -> ProviderHttpClient:
    return ProviderHttpClient(
        provider_key=capability.key,
        provider_version=capability.version,
        allowed_hosts=capability.allowed_hosts,
        transport=transport or HttpxSearchHttpTransport(),
        user_agent=config.polite_user_agent,
        timeout_seconds=config.timeout_seconds,
        max_response_bytes=config.max_response_bytes,
        max_attempts=config.max_attempts,
        backoff_base_seconds=config.backoff_base_seconds,
        backoff_cap_seconds=config.backoff_cap_seconds,
        min_interval_seconds=config.min_interval_seconds,
        sensitive_param_keys=sensitive_param_keys,
    )


def _json_response(
    client: ProviderHttpClient, response: SearchHttpResponse, page_number: int
) -> dict[str, Any]:
    try:
        value = json.loads(response.content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise client.invalid_response(
            page_number=page_number, message="provider returned invalid JSON"
        ).with_attempts(tuple(client.attempts)) from exc
    if not isinstance(value, dict):
        raise client.invalid_response(
            page_number=page_number, message="provider JSON root must be an object"
        ).with_attempts(tuple(client.attempts))
    return value


def _integer(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be an integer") from exc
    else:
        raise ValueError(f"{label} must be an integer")
    if result < 0:
        raise ValueError(f"{label} must not be negative")
    return result


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _doi(value: object) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.casefold().startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return normalized.casefold()


def _year(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and 1000 <= value <= 9999:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value[:4])
        except ValueError:
            return None
        return parsed if 1000 <= parsed <= 9999 else None
    return None


def _citation(
    *,
    source_key: object,
    title: object,
    abstract: object,
    year: object,
    doi: object,
    pmid: object,
    authors: list[str],
    journal: object,
    raw_metadata: dict[str, object],
) -> ParsedCitation:
    clean_title = _text(title)
    if clean_title is None:
        raise ValueError("provider citation is missing a title")
    clean_pmid = _text(pmid)
    if clean_pmid is not None and not clean_pmid.isdigit():
        clean_pmid = None
    return ParsedCitation(
        source_key=_text(source_key),
        title=clean_title,
        abstract=_text(abstract),
        publication_year=_year(year),
        doi=_doi(doi),
        pmid=clean_pmid,
        authors=[item for value in authors if (item := _text(value)) is not None],
        journal=_text(journal),
        raw_metadata=raw_metadata,
    )


def _append_raw(
    bodies: list[bytes],
    content: bytes,
    *,
    max_bytes: int,
    attempts: tuple[ProviderAttemptSnapshot, ...],
) -> None:
    size = sum(len(item) for item in bodies) + len(content)
    if size > max_bytes:
        raise SearchProviderError(
            "aggregate provider response exceeds the configured raw-artifact limit",
            failure_class=ProviderFailureClass.BLOCKED,
            response_byte_size=size,
            attempts=attempts,
        )
    bodies.append(content)


class OpenAlexSearchProvider(SearchProvider):
    capability = OPENALEX_CAPABILITY
    provider_key = OPENALEX_CAPABILITY.key
    version = OPENALEX_CAPABILITY.version

    def __init__(
        self,
        config: ProviderRuntimeConfig | None = None,
        transport: SearchHttpTransport | None = None,
    ) -> None:
        self._config = config or ProviderRuntimeConfig()
        self._transport = transport

    async def execute_search(
        self, query: str, filters: dict[str, str], *, max_pages: int, page_size: int
    ) -> SearchProviderResult:
        max_pages, page_size = _page_limits(self.capability, max_pages, page_size)
        client = _client(self.capability, self._config, self._transport)
        bodies: list[bytes] = []
        records: list[ParsedCitation] = []
        result_count = 0
        try:
            for page in range(1, max_pages + 1):
                params = {
                    "search": query,
                    "page": str(page),
                    "per-page": str(page_size),
                }
                if filters:
                    params["filter"] = ",".join(f"{key}:{filters[key]}" for key in sorted(filters))
                if self._config.contact_email:
                    params["mailto"] = self._config.contact_email
                response = await client.get(
                    url=self.capability.base_url, params=params, page_number=page
                )
                _append_raw(
                    bodies,
                    response.content,
                    max_bytes=self._config.max_aggregate_raw_bytes,
                    attempts=tuple(client.attempts),
                )
                try:
                    payload = _json_response(client, response, page)
                    meta = payload.get("meta")
                    items = payload.get("results")
                    if not isinstance(meta, dict) or not isinstance(items, list):
                        raise ValueError("OpenAlex response is missing meta/results")
                    result_count = _integer(meta.get("count"), label="OpenAlex result count")
                    records.extend(self._normalize(item) for item in items)
                except SearchProviderError:
                    raise
                except (TypeError, ValueError, KeyError) as exc:
                    raise client.invalid_response(
                        page_number=page, message=f"invalid OpenAlex response: {exc}"
                    ).with_attempts(tuple(client.attempts)) from exc
                if not items or len(records) >= result_count or len(items) < page_size:
                    break
        except SearchProviderError as exc:
            raise exc.with_attempts(tuple(client.attempts)) from exc
        return SearchProviderResult(
            exact_query=query,
            filters=dict(filters),
            provider_result_count=result_count,
            raw_content=b"\n".join(bodies),
            raw_media_type=self.capability.default_media_type,
            provider_key=self.provider_key,
            provider_version=self.version,
            records=tuple(records),
            attempts=tuple(client.attempts),
        )

    @staticmethod
    def _normalize(item: object) -> ParsedCitation:
        if not isinstance(item, dict):
            raise ValueError("OpenAlex result must be an object")
        abstract: str | None = None
        inverted = item.get("abstract_inverted_index")
        if isinstance(inverted, dict):
            positions: list[tuple[int, str]] = []
            for word, indexes in inverted.items():
                if isinstance(word, str) and isinstance(indexes, list):
                    positions.extend(
                        (index, word)
                        for index in indexes
                        if isinstance(index, int) and not isinstance(index, bool)
                    )
            abstract = " ".join(word for _, word in sorted(positions)) or None
        authors: list[str] = []
        authorships = item.get("authorships")
        if isinstance(authorships, list):
            for authorship in authorships:
                if isinstance(authorship, dict):
                    author = authorship.get("author")
                    if isinstance(author, dict) and isinstance(author.get("display_name"), str):
                        authors.append(author["display_name"])
        location = item.get("primary_location")
        journal: object = None
        if isinstance(location, dict):
            source = location.get("source")
            if isinstance(source, dict):
                journal = source.get("display_name")
        ids = item.get("ids")
        pmid: object = None
        if isinstance(ids, dict):
            pmid_value = ids.get("pmid")
            pmid = pmid_value.rsplit("/", 1)[-1] if isinstance(pmid_value, str) else pmid_value
        return _citation(
            source_key=item.get("id"),
            title=item.get("title") or item.get("display_name"),
            abstract=abstract,
            year=item.get("publication_year"),
            doi=item.get("doi"),
            pmid=pmid,
            authors=authors,
            journal=journal,
            raw_metadata={"provider": "openalex", "record": item},
        )


class EuropePmcSearchProvider(SearchProvider):
    capability = EUROPE_PMC_CAPABILITY
    provider_key = EUROPE_PMC_CAPABILITY.key
    version = EUROPE_PMC_CAPABILITY.version

    def __init__(
        self,
        config: ProviderRuntimeConfig | None = None,
        transport: SearchHttpTransport | None = None,
    ) -> None:
        self._config = config or ProviderRuntimeConfig()
        self._transport = transport

    async def execute_search(
        self, query: str, filters: dict[str, str], *, max_pages: int, page_size: int
    ) -> SearchProviderResult:
        max_pages, page_size = _page_limits(self.capability, max_pages, page_size)
        client = _client(self.capability, self._config, self._transport)
        bodies: list[bytes] = []
        records: list[ParsedCitation] = []
        result_count = 0
        provider_query = self._query_with_filters(query, filters)
        try:
            for page in range(1, max_pages + 1):
                response = await client.get(
                    url=self.capability.base_url,
                    params={
                        "query": provider_query,
                        "format": "json",
                        "resultType": "core",
                        "pageSize": str(page_size),
                        "page": str(page),
                    },
                    page_number=page,
                )
                _append_raw(
                    bodies,
                    response.content,
                    max_bytes=self._config.max_aggregate_raw_bytes,
                    attempts=tuple(client.attempts),
                )
                try:
                    payload = _json_response(client, response, page)
                    result_count = _integer(payload.get("hitCount"), label="Europe PMC hit count")
                    result_list = payload.get("resultList")
                    items = result_list.get("result") if isinstance(result_list, dict) else None
                    if not isinstance(items, list):
                        raise ValueError("Europe PMC response is missing resultList.result")
                    records.extend(self._normalize(item) for item in items)
                except SearchProviderError:
                    raise
                except (TypeError, ValueError, KeyError) as exc:
                    raise client.invalid_response(
                        page_number=page, message=f"invalid Europe PMC response: {exc}"
                    ).with_attempts(tuple(client.attempts)) from exc
                if not items or len(records) >= result_count or len(items) < page_size:
                    break
        except SearchProviderError as exc:
            raise exc.with_attempts(tuple(client.attempts)) from exc
        return SearchProviderResult(
            exact_query=query,
            filters=dict(filters),
            provider_result_count=result_count,
            raw_content=b"\n".join(bodies),
            raw_media_type=self.capability.default_media_type,
            provider_key=self.provider_key,
            provider_version=self.version,
            records=tuple(records),
            attempts=tuple(client.attempts),
        )

    @staticmethod
    def _query_with_filters(query: str, filters: dict[str, str]) -> str:
        additions: list[str] = []
        if filters.get("from_year"):
            additions.append(f"FIRST_PDATE:[{filters['from_year']}-01-01 TO *]")
        if filters.get("to_year"):
            additions.append(f"FIRST_PDATE:[* TO {filters['to_year']}-12-31]")
        return f"({query}) AND " + " AND ".join(additions) if additions else query

    @staticmethod
    def _normalize(item: object) -> ParsedCitation:
        if not isinstance(item, dict):
            raise ValueError("Europe PMC result must be an object")
        authors: list[str] = []
        author_list = item.get("authorList")
        if isinstance(author_list, dict):
            author_items = author_list.get("author")
            if isinstance(author_items, list):
                authors = [
                    author.get("fullName", "")
                    for author in author_items
                    if isinstance(author, dict)
                ]
        return _citation(
            source_key=item.get("id"),
            title=item.get("title"),
            abstract=item.get("abstractText"),
            year=item.get("pubYear"),
            doi=item.get("doi"),
            pmid=item.get("pmid"),
            authors=authors or [_text(item.get("authorString")) or ""],
            journal=item.get("journalTitle"),
            raw_metadata={"provider": "europe-pmc", "record": item},
        )


class PubMedSearchProvider(SearchProvider):
    capability = PUBMED_CAPABILITY
    provider_key = PUBMED_CAPABILITY.key
    version = PUBMED_CAPABILITY.version
    _fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(
        self,
        config: ProviderRuntimeConfig | None = None,
        transport: SearchHttpTransport | None = None,
    ) -> None:
        self._config = config or ProviderRuntimeConfig()
        self._transport = transport

    async def execute_search(
        self, query: str, filters: dict[str, str], *, max_pages: int, page_size: int
    ) -> SearchProviderResult:
        max_pages, page_size = _page_limits(self.capability, max_pages, page_size)
        client = _client(
            self.capability,
            self._config,
            self._transport,
            sensitive_param_keys=frozenset({"api_key"}),
        )
        bodies: list[bytes] = []
        records: list[ParsedCitation] = []
        result_count = 0
        try:
            for page in range(1, max_pages + 1):
                search_params = {
                    "db": "pubmed",
                    "term": query,
                    "retstart": str((page - 1) * page_size),
                    "retmax": str(page_size),
                    "retmode": "json",
                    "tool": "research-tool",
                    "email": self._config.contact_email or "",
                }
                if self._config.pubmed_api_key:
                    search_params["api_key"] = self._config.pubmed_api_key
                response = await client.get(
                    url=self.capability.base_url, params=search_params, page_number=page
                )
                _append_raw(
                    bodies,
                    response.content,
                    max_bytes=self._config.max_aggregate_raw_bytes,
                    attempts=tuple(client.attempts),
                )
                try:
                    payload = _json_response(client, response, page)
                    search_result = payload.get("esearchresult")
                    if not isinstance(search_result, dict):
                        raise ValueError("PubMed response is missing esearchresult")
                    result_count = _integer(search_result.get("count"), label="PubMed result count")
                    ids = search_result.get("idlist")
                    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
                        raise ValueError("PubMed response is missing idlist")
                except SearchProviderError:
                    raise
                except (TypeError, ValueError, KeyError) as exc:
                    raise client.invalid_response(
                        page_number=page, message=f"invalid PubMed search response: {exc}"
                    ).with_attempts(tuple(client.attempts)) from exc
                if not ids:
                    break
                fetch_params = {
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "retmode": "xml",
                    "rettype": "abstract",
                    "tool": "research-tool",
                    "email": self._config.contact_email or "",
                }
                if self._config.pubmed_api_key:
                    fetch_params["api_key"] = self._config.pubmed_api_key
                fetch_response = await client.get(
                    url=self._fetch_url, params=fetch_params, page_number=page
                )
                _append_raw(
                    bodies,
                    fetch_response.content,
                    max_bytes=self._config.max_aggregate_raw_bytes,
                    attempts=tuple(client.attempts),
                )
                try:
                    records.extend(self._normalize(fetch_response.content))
                except (ET.ParseError, TypeError, ValueError) as exc:
                    raise client.invalid_response(
                        page_number=page, message=f"invalid PubMed XML response: {exc}"
                    ).with_attempts(tuple(client.attempts)) from exc
                if len(records) >= result_count or len(ids) < page_size:
                    break
        except SearchProviderError as exc:
            raise exc.with_attempts(tuple(client.attempts)) from exc
        return SearchProviderResult(
            exact_query=query,
            filters=dict(filters),
            provider_result_count=result_count,
            raw_content=b"\n".join(bodies),
            raw_media_type=self.capability.default_media_type,
            provider_key=self.provider_key,
            provider_version=self.version,
            records=tuple(records),
            attempts=tuple(client.attempts),
        )

    @staticmethod
    def _normalize(content: bytes) -> list[ParsedCitation]:
        root = ET.fromstring(content)
        records: list[ParsedCitation] = []
        for article in root.findall(".//PubmedArticle"):
            medline = article.find(".//MedlineCitation")
            article_node = medline.find("./Article") if medline is not None else None
            if article_node is None:
                raise ValueError("PubMed article is missing Article")
            title_node = article_node.find("./ArticleTitle")
            title = "".join(title_node.itertext()) if title_node is not None else None
            abstract = " ".join(
                "".join(node.itertext()) for node in article_node.findall("./Abstract/AbstractText")
            )
            journal_node = article_node.find("./Journal/Title")
            authors: list[str] = []
            for author in article_node.findall("./AuthorList/Author"):
                collective = author.findtext("./CollectiveName")
                if collective:
                    authors.append(collective)
                    continue
                last = author.findtext("./LastName") or ""
                initials = author.findtext("./Initials") or ""
                authors.append(" ".join(value for value in (last, initials) if value))
            pmid = medline.findtext("./PMID") if medline is not None else None
            doi: str | None = None
            for identifier in article.findall(".//ArticleId"):
                if identifier.attrib.get("IdType", "").casefold() == "doi":
                    doi = identifier.text
                    break
            records.append(
                _citation(
                    source_key=pmid,
                    title=title,
                    abstract=abstract,
                    year=article_node.findtext("./Journal/JournalIssue/PubDate/Year")
                    or article_node.findtext("./Journal/JournalIssue/PubDate/MedlineDate"),
                    doi=doi,
                    pmid=pmid,
                    authors=authors,
                    journal=journal_node.text if journal_node is not None else None,
                    raw_metadata={"provider": "pubmed", "pmid": pmid},
                )
            )
        return records


class FixtureSearchProvider(SearchProvider):
    capability = FIXTURE_CAPABILITY
    provider_key = FIXTURE_CAPABILITY.key
    version = FIXTURE_CAPABILITY.version

    def __init__(self, records: tuple[ParsedCitation, ...] = ()) -> None:
        self._records = records

    async def execute_search(
        self, query: str, filters: dict[str, str], *, max_pages: int, page_size: int
    ) -> SearchProviderResult:
        max_pages, page_size = _page_limits(self.capability, max_pages, page_size)
        limited = self._records[: max_pages * page_size]
        raw = json.dumps(
            [asdict(record) for record in limited],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        now = datetime.now(UTC)
        attempt = ProviderAttemptSnapshot(
            provider_key=self.provider_key,
            provider_version=self.version,
            page_number=1,
            attempt_number=1,
            request_fingerprint=ProviderAttemptSnapshot.request_hash(
                "fixture://offline", {"query": query}
            ),
            started_at=now,
            completed_at=now,
            http_status=None,
            failure_class=None,
            response_byte_size=len(raw),
            response_sha256=None,
            note="offline deterministic fixture",
        )
        return SearchProviderResult(
            exact_query=query,
            filters=dict(filters),
            provider_result_count=len(self._records),
            raw_content=raw,
            raw_media_type=self.capability.default_media_type,
            provider_key=self.provider_key,
            provider_version=self.version,
            records=limited,
            attempts=(attempt,),
        )


class SearchProviderRegistry:
    def __init__(self, providers: tuple[SearchProvider, ...]) -> None:
        self._providers = {provider.provider_key.casefold(): provider for provider in providers}

    def get(self, provider_key: str) -> SearchProvider | None:
        return self._providers.get(provider_key.strip().casefold())

    def capabilities(self) -> list[SearchProviderCapability]:
        return sorted(
            (provider.capability for provider in self._providers.values()),
            key=lambda item: item.key,
        )

    @classmethod
    def default(
        cls,
        config: ProviderRuntimeConfig | None = None,
        transport: SearchHttpTransport | None = None,
        fixture_records: tuple[ParsedCitation, ...] = (),
    ) -> SearchProviderRegistry:
        resolved = config or ProviderRuntimeConfig()
        return cls(
            (
                FixtureSearchProvider(fixture_records),
                OpenAlexSearchProvider(resolved, transport),
                PubMedSearchProvider(resolved, transport),
                EuropePmcSearchProvider(resolved, transport),
            )
        )

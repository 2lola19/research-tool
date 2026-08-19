from __future__ import annotations

import pytest

from backend.app.citations.domain import ParsedCitation
from backend.app.search.provider_adapters import (
    EuropePmcSearchProvider,
    FixtureSearchProvider,
    OpenAlexSearchProvider,
    ProviderRuntimeConfig,
    PubMedSearchProvider,
)
from backend.app.search.provider_domain import (
    ProviderFailureClass,
    SearchProviderError,
)
from backend.app.search.provider_http import (
    ProviderHttpClient,
    SearchHttpResponse,
    SearchHttpTransport,
    build_polite_user_agent,
    validate_provider_url,
)


class FakeTransport(SearchHttpTransport):
    def __init__(self, responses: list[SearchHttpResponse | Exception]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, dict[str, str]]] = []

    async def get(
        self,
        *,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> SearchHttpResponse:
        del headers, timeout_seconds, max_response_bytes
        self.requests.append((url, params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(body: str, status_code: int = 200, **headers: str) -> SearchHttpResponse:
    return SearchHttpResponse(status_code, headers, body.encode())


def _citation(title: str, source_key: str) -> ParsedCitation:
    return ParsedCitation(
        source_key=source_key,
        title=title,
        abstract=None,
        publication_year=2026,
        doi=None,
        pmid=None,
        authors=[],
        journal=None,
        raw_metadata={"fixture": source_key},
    )


@pytest.mark.asyncio
async def test_openalex_normalizes_records_and_stops_at_bounded_pages() -> None:
    transport = FakeTransport(
        [
            _response(
                '{"meta":{"count":2},"results":[{"id":"https://openalex.org/W1",'
                '"title":"First","publication_year":2025,"abstract_inverted_index":'
                '{"first":[1],"abstract":[0]},"authorships":[{"author":'
                '{"display_name":"A Author"}}],"primary_location":{"source":'
                '{"display_name":"Journal"}},"ids":{"pmid":"https://pubmed.ncbi.nlm.nih.gov/1"}}]}'
            ),
            _response(
                '{"meta":{"count":2},"results":[{"id":"https://openalex.org/W2",'
                '"title":"Second","publication_year":2024,"authorships":[],"ids":{}}]}'
            ),
        ]
    )
    provider = OpenAlexSearchProvider(
        ProviderRuntimeConfig(min_interval_seconds=0), transport=transport
    )

    result = await provider.execute_search("systematic review", {}, max_pages=2, page_size=1)

    assert result.provider_result_count == 2
    assert [record.title for record in result.records] == ["First", "Second"]
    assert result.records[0].abstract == "abstract first"
    assert result.records[0].pmid == "1"
    assert len(result.attempts) == 2
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_europe_pmc_normalizes_authors_and_year_filters_without_live_network() -> None:
    transport = FakeTransport(
        [
            _response(
                '{"hitCount":1,"resultList":{"result":[{"id":"PMC1",'
                '"title":"Europe record","abstractText":"Abstract",'
                '"pubYear":"2023","pmid":"42","doi":"10.1000/Example",'
                '"authorList":{"author":[{"fullName":"A Author"}]},'
                '"journalTitle":"Journal"}]}}'
            )
        ]
    )
    provider = EuropePmcSearchProvider(
        ProviderRuntimeConfig(min_interval_seconds=0), transport=transport
    )

    result = await provider.execute_search(
        "exercise",
        {"from_year": "2020", "to_year": "2024"},
        max_pages=1,
        page_size=10,
    )

    assert result.records[0].doi == "10.1000/example"
    assert result.records[0].authors == ["A Author"]
    assert "FIRST_PDATE" in transport.requests[0][1]["query"]


@pytest.mark.asyncio
async def test_pubmed_normalizes_search_and_fetch_fixtures() -> None:
    transport = FakeTransport(
        [
            _response('{"esearchresult":{"count":"1","idlist":["123"]}}'),
            _response(
                "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID>"
                "<Article><ArticleTitle>PubMed title</ArticleTitle><Abstract>"
                "<AbstractText>PubMed abstract</AbstractText></Abstract><Journal>"
                "<Title>PubMed journal</Title><JournalIssue><PubDate><Year>2022</Year>"
                "</PubDate></JournalIssue></Journal><AuthorList><Author><LastName>Doe</LastName>"
                "<Initials>J</Initials></Author></AuthorList></Article></MedlineCitation>"
                '<PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/PMID</ArticleId>'
                "</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"
            ),
        ]
    )
    provider = PubMedSearchProvider(
        ProviderRuntimeConfig(min_interval_seconds=0), transport=transport
    )

    result = await provider.execute_search("exercise", {}, max_pages=1, page_size=10)

    assert result.provider_result_count == 1
    assert result.records[0].title == "PubMed title"
    assert result.records[0].authors == ["Doe J"]
    assert result.records[0].doi == "10.1000/pmid"
    assert len(result.attempts) == 2


@pytest.mark.asyncio
async def test_provider_http_retries_rate_limits_with_bounded_attempt_history() -> None:
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    transport = FakeTransport([_response("busy", 429, **{"retry-after": "0"}), _response("ok")])
    client = ProviderHttpClient(
        provider_key="fixture",
        provider_version="fixture-1",
        allowed_hosts=frozenset({"api.example.org"}),
        transport=transport,
        user_agent="test",
        timeout_seconds=1,
        max_response_bytes=100,
        max_attempts=2,
        min_interval_seconds=0,
        sleep=record_sleep,
    )

    response = await client.get(
        url="https://api.example.org/search",
        params={"q": "exercise"},
        page_number=1,
    )

    assert response.content == b"ok"
    assert [attempt.failure_class for attempt in client.attempts] == [
        ProviderFailureClass.RATE_LIMITED,
        None,
    ]
    assert sleeps == [0]


@pytest.mark.asyncio
async def test_provider_raw_response_and_url_boundaries_are_enforced() -> None:
    transport = FakeTransport([_response('{"meta":{"count":0},"results":[]}')])
    provider = OpenAlexSearchProvider(
        ProviderRuntimeConfig(min_interval_seconds=0, max_aggregate_raw_bytes=10),
        transport=transport,
    )

    with pytest.raises(SearchProviderError) as error:
        await provider.execute_search("query", {}, max_pages=1, page_size=1)
    assert error.value.failure_class is ProviderFailureClass.BLOCKED

    with pytest.raises(SearchProviderError, match="allowlist"):
        validate_provider_url("http://api.openalex.org/works", frozenset({"api.openalex.org"}))
    with pytest.raises(SearchProviderError, match="non-public"):
        validate_provider_url("https://127.0.0.1/works", frozenset({"127.0.0.1"}))


@pytest.mark.asyncio
async def test_fixture_provider_is_deterministic_and_bounded() -> None:
    provider = FixtureSearchProvider((_citation("First", "1"), _citation("Second", "2")))

    first = await provider.execute_search("query", {}, max_pages=1, page_size=1)
    second = await provider.execute_search("query", {}, max_pages=1, page_size=1)

    assert first.raw_content == second.raw_content
    assert first.provider_result_count == 2
    assert [record.title for record in first.records] == ["First"]


def test_provider_user_agent_rejects_header_injection() -> None:
    assert build_polite_user_agent("ResearchTool/0.1", "team@example.org") == (
        "ResearchTool/0.1 (+mailto:team@example.org)"
    )
    with pytest.raises(ValueError):
        build_polite_user_agent("ResearchTool", "team@example.org\r\nX-Leak: value")

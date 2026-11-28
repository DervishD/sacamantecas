"""Test suite for the URL processing functions."""
import logging
import re
from typing import TYPE_CHECKING

import pytest

from sacamantecas import (
    BaseParser,
    collect_urls,
    Debug,
    Gateway,
    GatewayError,
    get_parser,
    logger,
    lowercase_first_letter,
    Messages,
    Metadata,
    ParserConfig,
    process_urls,
    Profile,
    ProfileError,
    saca_las_mantecas,
    save_results,
    SkimmingError,
)
from tests.test_parsers import BASE_STRING

if TYPE_CHECKING:
    from sacamantecas import SkimResults, Url


URL_A = 'xx://host.domain_a.tld/a'
URL_A_PATTERN = re.compile(re.escape(URL_A))
URL_B = 'xx://host.domain_b.tld/b'
URL_C = 'xx://host.domain_c.tld/c'
SOURCE = 'a_source_label'

SAMPLE_MESSAGE = 'some message'
SAMPLE_METADATA_BY_URL = {
    URL_A: {'A sample key A': 'A sample value A'},
    URL_B: {'A sample key B': 'A sample value B'},
    URL_C: {'A sample key C': 'A sample value C'},
}
SAMPLE_PROFILES = (Profile('A profile name', re.compile('sample_profile'), BaseParser(), {}),)

FAILED_URL_EXCEPTION_CASES = [
    pytest.param(
        ProfileError(Messages.PROFILE_ERROR_NO_MATCHING_PROFILE),
        id='profile_error',
    ),
    pytest.param(
        SkimmingError(Messages.SKIMMING_ERROR_NO_CONTENTS),
        id='skimming_error',
    ),
]


class StubGateway(Gateway):
    """Minimal concrete gateway with canned URLs and an optional exception."""

    def __init__(self, source: str, urls: list[Url] | None = None, exception: Exception | None = None) -> None:
        """Initialize object."""
        super().__init__(source)
        self.stub_urls = urls or []
        self.stub_exception = exception

    def _get_urls(self) -> list[Url]:
        """Raise the canned exception, if any, otherwise return the canned URLs."""
        if self.stub_exception is not None:
            raise self.stub_exception
        return list(self.stub_urls)

    def _save_metadata(self, results: SkimResults) -> None:
        """Not used by these tests."""
        raise NotImplementedError


# pylint: disable-next=unused-variable
def test_collect_urls_returns_urls() -> None:
    """Test `collect_urls()` returns the URLs the gateway provides."""
    urls = [URL_A, URL_B, URL_C]
    assert collect_urls(StubGateway(SOURCE, urls)) == urls


# pylint: disable-next=unused-variable
def test_collect_urls_gateway_error(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `collect_urls()` warns about `GatewayError` being raised.

    In that case, it should return no URLs.
    """
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.WARNING)
    gateway = StubGateway(SOURCE, exception=GatewayError(Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND))

    assert not collect_urls(gateway)
    assert [record.getMessage() for record in caplog.records] == [
        f'{Messages.WARNING_PREFIX}{lowercase_first_letter(Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND)}',
    ]


# pylint: disable-next=unused-variable
def test_collect_urls_gateway_error_logging(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `collect_urls()` logs `GatewayError` properly.

    It should log it with `logging.DEBUG` level.
    """
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)
    gateway = StubGateway(SOURCE, exception=GatewayError(Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND))

    collect_urls(gateway)
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG] == [
        Debug.EXCEPTION_LOG.format(GatewayError.__name__),
        Debug.EXCEPTION_LOG_NO_CONTEXT,
    ]


# pylint: disable-next=unused-variable
def test_collect_urls_empty_source(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `collect_urls()` warns for empty gateways.

    It should also return none, as the gateway provides no URLs.
    """
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.WARNING)

    assert not collect_urls(StubGateway(SOURCE))
    assert [record.getMessage() for record in caplog.records] == [
        f'{Messages.WARNING_PREFIX}{lowercase_first_letter(Messages.WARNING_GATEWAY_EMPTY)}',
    ]


# pylint: disable-next=unused-variable
def test_collect_urls_propagates_other_exceptions() -> None:
    """Test `collect_urls()` only catches `GatewayError` exceptions."""
    gateway = StubGateway(SOURCE, exception=RuntimeError(SAMPLE_MESSAGE))

    with pytest.raises(RuntimeError, match=SAMPLE_MESSAGE):
        collect_urls(gateway)


# pylint: disable-next=unused-variable
def test_process_urls_returns_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `process_urls()` returns the metadata of every URL, in the order of the URLs."""

    def mock_get_parser(*_args: object) -> BaseParser:
        """Return a parser, whatever the URL."""
        return BaseParser()

    def mock_saca_las_mantecas(url: Url, *_args: object) -> Metadata:
        """Return the canned metadata for *url*."""
        return SAMPLE_METADATA_BY_URL[url]

    monkeypatch.setattr('sacamantecas.get_parser', mock_get_parser)
    monkeypatch.setattr('sacamantecas.saca_las_mantecas', mock_saca_las_mantecas)

    results = process_urls(list(SAMPLE_METADATA_BY_URL), ())
    assert list(results.items()) == list(SAMPLE_METADATA_BY_URL.items())


# pylint: disable-next=unused-variable
def test_process_urls_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `process_urls()` wires parsers and profiles properly.

    It should gets the parsers using the given profiles and skims each
    URL with its corresponding parser.
    """
    parsers_by_url = {url: BaseParser() for url in SAMPLE_METADATA_BY_URL}
    get_parser_calls: list[tuple[Url, tuple[Profile, ...]]] = []
    skimming_calls: list[tuple[Url, BaseParser]] = []

    def mock_get_parser(url: Url, profiles: tuple[Profile, ...]) -> BaseParser:
        """Record the call and return the parser assigned to *url*."""
        get_parser_calls.append((url, profiles))
        return parsers_by_url[url]

    def mock_saca_las_mantecas(url: Url, parser: BaseParser) -> Metadata:
        """Record the call and return the canned metadata for *url*."""
        skimming_calls.append((url, parser))
        return SAMPLE_METADATA_BY_URL[url]

    monkeypatch.setattr('sacamantecas.get_parser', mock_get_parser)
    monkeypatch.setattr('sacamantecas.saca_las_mantecas', mock_saca_las_mantecas)

    process_urls(list(SAMPLE_METADATA_BY_URL), SAMPLE_PROFILES)
    assert get_parser_calls == [(url, SAMPLE_PROFILES) for url in SAMPLE_METADATA_BY_URL]
    assert skimming_calls == list(parsers_by_url.items())


@pytest.mark.parametrize('exception', FAILED_URL_EXCEPTION_CASES)
# pylint: disable-next=unused-variable
def test_process_urls_skips_failed_urls(exception: Exception, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `process_urls()` leaves out the URLs which fail.

    It should keep processing the rest, though.
    """

    def mock_get_parser(*_args: object) -> BaseParser:
        """Return a parser, whatever the URL."""
        return BaseParser()

    def mock_saca_las_mantecas(url: Url, *_args: object) -> Metadata:
        """Raise *exception* ONLY for `URL_C`, return for the rest."""
        if url == URL_C:
            raise exception
        return SAMPLE_METADATA_BY_URL[url]

    monkeypatch.setattr('sacamantecas.get_parser', mock_get_parser)
    monkeypatch.setattr('sacamantecas.saca_las_mantecas', mock_saca_las_mantecas)

    results = process_urls([URL_C, URL_B, URL_A], ())
    assert list(results.items()) == [(URL_B, SAMPLE_METADATA_BY_URL[URL_B]), (URL_A, SAMPLE_METADATA_BY_URL[URL_A])]


@pytest.mark.parametrize('exception', FAILED_URL_EXCEPTION_CASES)
# pylint: disable-next=unused-variable
def test_process_urls_warns_about_failed_urls(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
) -> None:
    """Test `process_urls()` warns about each URL which fails."""
    def mock_get_parser(*_args: object) -> BaseParser:
        """Return a parser, whatever the URL."""
        return BaseParser()

    def mock_saca_las_mantecas(*_args: object) -> Metadata:
        """Raise *exception*, whatever the URL."""
        raise exception

    monkeypatch.setattr(logger, 'propagate', True)
    monkeypatch.setattr('sacamantecas.get_parser', mock_get_parser)
    monkeypatch.setattr('sacamantecas.saca_las_mantecas', mock_saca_las_mantecas)
    caplog.set_level(logging.WARNING)

    process_urls([URL_C], ())
    assert [record.getMessage().lstrip() for record in caplog.records] == [
        f'{Messages.WARNING_PREFIX}{lowercase_first_letter(str(exception))}',
    ]


@pytest.mark.parametrize('exception', FAILED_URL_EXCEPTION_CASES)
# pylint: disable-next=unused-variable
def test_process_urls_failed_urls_debug_log(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
) -> None:
    """Test `process_urls()` logs failed-URLs exception properly."""

    def mock_get_parser(*_args: object) -> BaseParser:
        """Return a parser, whatever the URL."""
        return BaseParser()

    def mock_saca_las_mantecas(*_args: object) -> Metadata:
        """Raise *exception*, whatever the URL."""
        raise exception

    monkeypatch.setattr(logger, 'propagate', True)
    monkeypatch.setattr('sacamantecas.get_parser', mock_get_parser)
    monkeypatch.setattr('sacamantecas.saca_las_mantecas', mock_saca_las_mantecas)
    caplog.set_level(logging.DEBUG)

    process_urls([URL_C], ())

    assert [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG] == [
        Debug.EXCEPTION_LOG.format(type(exception).__name__),
        Debug.EXCEPTION_LOG_NO_CONTEXT,
    ]


@pytest.mark.parametrize(('urls', 'failed_urls', 'expected'), [
    pytest.param(
        [URL_A, URL_B],
        (URL_A, URL_B),
        Messages.URLS_RESULT_NONE.format(0, 2),
        id='none',
    ),
    pytest.param(
        [URL_A, URL_B],
        (URL_B,),
        Messages.URLS_RESULT_ONE.format(1, 2),
        id='one',
    ),
    pytest.param(
        [URL_A, URL_B, URL_C],
        (URL_C,),
        Messages.URLS_RESULT_MANY.format(2, 3),
        id='many',
    ),
])
# pylint: disable-next=unused-variable
def test_process_urls_summary(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    urls: list[Url],
    failed_urls: tuple[Url, ...],
    expected: str,
) -> None:
    """Test `process_urls()` logs the summary properly.

    It should log the processed URLs and the total, as the last message.
    """
    def mock_get_parser(*_args: object) -> BaseParser:
        """Return a parser, whatever the URL."""
        return BaseParser()

    def mock_saca_las_mantecas(url: Url, *_args: object) -> Metadata:
        """Raise `SkimmingError` for the URLs in *failed_urls*.

        Return the canned metadata for the rest.
        """
        if url in failed_urls:
            raise SkimmingError(Messages.SKIMMING_ERROR_NO_CONTENTS)
        return SAMPLE_METADATA_BY_URL[url]

    monkeypatch.setattr(logger, 'propagate', True)
    monkeypatch.setattr('sacamantecas.get_parser', mock_get_parser)
    monkeypatch.setattr('sacamantecas.saca_las_mantecas', mock_saca_las_mantecas)
    caplog.set_level(logging.INFO)

    process_urls(urls, ())
    assert [record.getMessage() for record in caplog.records][-1] == Messages.URLS_RESULT.format(expected)


# pylint: disable-next=unused-variable
def test_process_urls_propagates_other_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `process_urls()` propagates other exceptions.

    It should only catch `ProfileError` and `SkimmingError`, propagating
    all others.
    """

    def mock_get_parser(*_args: object) -> BaseParser:
        """Return a parser, whatever the URL."""
        return BaseParser()

    def mock_saca_las_mantecas(*_args: object) -> Metadata:
        """Raise an exception which `process_urls()` is not expected to handle."""
        raise RuntimeError(SAMPLE_MESSAGE)

    monkeypatch.setattr('sacamantecas.get_parser', mock_get_parser)
    monkeypatch.setattr('sacamantecas.saca_las_mantecas', mock_saca_las_mantecas)

    with pytest.raises(RuntimeError, match=SAMPLE_MESSAGE):
        process_urls([URL_A], ())


# pylint: disable-next=unused-variable
def test_saca_las_mantecas_returns_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `saca_las_mantecas()` returns the obtained metadata."""
    def mock_retrieve_url(*_args: object) -> str:
        """Return the mock contents, whatever the URL."""
        return BASE_STRING

    def mock_feed(*_args: object) -> None:
        """Do nothing, the parser is not under test."""

    def mock_get_metadata(*_args: object) -> Metadata:
        """Return the canned metadata."""
        return SAMPLE_METADATA_BY_URL[URL_A]

    parser = BaseParser()
    monkeypatch.setattr('sacamantecas.retrieve_url', mock_retrieve_url)
    monkeypatch.setattr(parser, 'feed', mock_feed)
    monkeypatch.setattr(parser, 'close', lambda: None)
    monkeypatch.setattr(parser, 'get_metadata', mock_get_metadata)

    assert saca_las_mantecas(URL_A, parser) == SAMPLE_METADATA_BY_URL[URL_A]


# pylint: disable-next=unused-variable
def test_saca_las_mantecas_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `saca_las_mantecas()` wiring.

    It should retrieve the URL, feed the contents to the parser and then
    close it, and finally ask for the metadata.
    """
    recorded_calls: list[tuple[str, str | None]] = []

    def mock_retrieve_url(url: Url) -> str:
        """Record the call and return the mock contents."""
        recorded_calls.append(('retrieve_url', url))
        return BASE_STRING

    def mock_feed(contents: str) -> None:
        """Record the call."""
        recorded_calls.append(('feed', contents))

    def mock_close() -> None:
        """Record the call."""
        recorded_calls.append(('close', None))

    def mock_get_metadata() -> Metadata:
        """Record the call and return the canned metadata."""
        recorded_calls.append(('get_metadata', None))
        return SAMPLE_METADATA_BY_URL[URL_A]

    parser = BaseParser()
    monkeypatch.setattr('sacamantecas.retrieve_url', mock_retrieve_url)
    monkeypatch.setattr(parser, 'feed', mock_feed)
    monkeypatch.setattr(parser, 'close', mock_close)
    monkeypatch.setattr(parser, 'get_metadata', mock_get_metadata)

    saca_las_mantecas(URL_A, parser)
    assert recorded_calls == [
        ('retrieve_url', URL_A),
        ('feed', BASE_STRING),
        ('close', None),
        ('get_metadata', None),
    ]


# pylint: disable-next=unused-variable
def test_saca_las_mantecas_wraps_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `saca_las_mantecas()` wraps exceptions in `SkimmingError`.

    A retrieval error message is added, too.
    """
    error_message = BASE_STRING
    retrieval_failure = RuntimeError(SAMPLE_MESSAGE)

    def mock_retrieve_url(*_args: object) -> str:
        """Raise the retrieval failure, whatever the URL."""
        raise retrieval_failure

    def mock_retrieval_error_message(exception: Exception) -> str | None:
        """Return the canned message only for the retrieval failure."""
        return error_message if exception is retrieval_failure else None

    monkeypatch.setattr('sacamantecas.retrieve_url', mock_retrieve_url)
    monkeypatch.setattr('sacamantecas.retrieval_error_message', mock_retrieval_error_message)

    with pytest.raises(SkimmingError) as exc_info:
        saca_las_mantecas(URL_A, BaseParser())
    assert str(exc_info.value) == error_message
    assert exc_info.value.__cause__ is retrieval_failure


# pylint: disable-next=unused-variable
def test_saca_las_mantecas_propagates_unmapped_retrieval_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `saca_las_mantecas()` propagates some retrieval exceptions.

    It should propagate the retrieval exception unchanged if there is no
    corresponding error message from `retrieval_error_message()`.
    """
    retrieval_failure = RuntimeError(SAMPLE_MESSAGE)

    def mock_retrieve_url(*_args: object) -> str:
        """Raise the retrieval failure, whatever the URL."""
        raise retrieval_failure

    def mock_retrieval_error_message(*_args: object) -> None:
        """Return no message, whatever the exception."""

    monkeypatch.setattr('sacamantecas.retrieve_url', mock_retrieve_url)
    monkeypatch.setattr('sacamantecas.retrieval_error_message', mock_retrieval_error_message)

    with pytest.raises(RuntimeError) as exc_info:
        saca_las_mantecas(URL_A, BaseParser())
    assert exc_info.value is retrieval_failure


# pylint: disable-next=unused-variable
def test_saca_las_mantecas_empty_contents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `saca_las_mantecas()` raises for empty contents.

    It should rise a `SkimmingError`, without feeding the parser.
    """
    feed_calls: list[str] = []

    def mock_retrieve_url(*_args: object) -> str:
        """Return empty contents, whatever the URL."""
        return ''

    def mock_feed(contents: str) -> None:
        """Record the call."""
        feed_calls.append(contents)

    parser = BaseParser()
    monkeypatch.setattr('sacamantecas.retrieve_url', mock_retrieve_url)
    monkeypatch.setattr(parser, 'feed', mock_feed)

    with pytest.raises(SkimmingError) as exc_info:
        saca_las_mantecas(URL_A, parser)
    assert str(exc_info.value) == Messages.SKIMMING_ERROR_NO_CONTENTS
    assert not feed_calls


# pylint: disable-next=unused-variable
def test_saca_las_mantecas_no_metadata_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `saca_las_mantecas()` raises if there is no metadata.

    It should raise `SkimmingError` when the parser obtains no metadata.
    """
    def mock_retrieve_url(*_args: object) -> str:
        """Return the sample contents, whatever the URL."""
        return BASE_STRING

    def mock_feed(*_args: object) -> None:
        """Do nothing, the parser is not under test."""

    parser = BaseParser()
    monkeypatch.setattr('sacamantecas.retrieve_url', mock_retrieve_url)
    monkeypatch.setattr(parser, 'feed', mock_feed)
    monkeypatch.setattr(parser, 'close', lambda: None)
    monkeypatch.setattr(parser, 'get_metadata', dict)

    with pytest.raises(SkimmingError) as exc_info:
        saca_las_mantecas(URL_A, parser)
    assert str(exc_info.value) == Messages.SKIMMING_ERROR_NO_METADATA_FOUND


# pylint: disable-next=unused-variable
def test_save_results_saves_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `save_results()` saves the metadata properly.

    It should send the results to the gateway and return `True`.
    """
    saved_results: list[SkimResults] = []

    def mock_save_metadata(results: SkimResults) -> None:
        """Record the call."""
        saved_results.append(results)

    gateway = StubGateway(SOURCE)
    monkeypatch.setattr(gateway, 'save_metadata', mock_save_metadata)

    assert save_results(gateway, SAMPLE_METADATA_BY_URL) is True
    assert saved_results == [SAMPLE_METADATA_BY_URL]


# pylint: disable-next=unused-variable
def test_save_results_gateway_error(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `save_results()` warns about `GatewayError` exceptions.

    It should return `False` when it catches `GatewayError` exceptions.
    """
    def mock_save_metadata(*_args: object) -> None:
        """Raise a `GatewayError`, whatever the results."""
        raise GatewayError(Messages.GATEWAY_ERROR_NO_RESULTS_TO_SAVE)

    gateway = StubGateway(SOURCE)
    monkeypatch.setattr(logger, 'propagate', True)
    monkeypatch.setattr(gateway, 'save_metadata', mock_save_metadata)
    caplog.set_level(logging.WARNING)

    assert save_results(gateway, SAMPLE_METADATA_BY_URL) is False
    assert [record.getMessage() for record in caplog.records] == [
        f'{Messages.WARNING_PREFIX}{lowercase_first_letter(Messages.GATEWAY_ERROR_NO_RESULTS_TO_SAVE)}',
    ]

# pylint: disable-next=unused-variable
def test_save_results_gateway_error_debug_log(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test `save_results()` logs `GatewayError` exceptions properly.

    They should be logged with `logging.DEBUG` level.
    """

    def mock_save_metadata(*_args: object) -> None:
        """Raise a `GatewayError`, whatever the results."""
        raise GatewayError(Messages.GATEWAY_ERROR_NO_RESULTS_TO_SAVE)

    gateway = StubGateway(SOURCE)
    monkeypatch.setattr(logger, 'propagate', True)
    monkeypatch.setattr(gateway, 'save_metadata', mock_save_metadata)
    caplog.set_level(logging.DEBUG)

    save_results(gateway, SAMPLE_METADATA_BY_URL)
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG] == [
        Debug.EXCEPTION_LOG.format(GatewayError.__name__),
        Debug.EXCEPTION_LOG_NO_CONTEXT,
    ]


# pylint: disable-next=unused-variable
def test_save_results_propagates_other_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `save_results()` only catches `GatewayError` exceptions."""

    def mock_save_metadata(*_args: object) -> None:
        """Raise an exception which `save_results()` does to handle."""
        raise RuntimeError(BASE_STRING)

    gateway = StubGateway(SOURCE)
    monkeypatch.setattr(gateway, 'save_metadata', mock_save_metadata)

    with pytest.raises(RuntimeError, match=BASE_STRING):
        save_results(gateway, SAMPLE_METADATA_BY_URL)


# pylint: disable-next=unused-variable
def test_get_parser_returns_first_matching_parser() -> None:
    """Test `get_parser()` returns the first matching parser."""
    first_parser = BaseParser()
    second_parser = BaseParser()
    profiles = (
        Profile('Non matching profile', re.compile('this will NOT match'), BaseParser(), {}),
        Profile('First matching profile', URL_A_PATTERN, first_parser, {}),
        Profile('Second matching profile', URL_A_PATTERN, second_parser, {}),
    )

    assert get_parser(URL_A, profiles) is first_parser


# pylint: disable-next=unused-variable
def test_get_parser_configures_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `get_parser()` configures the parser properly.

    It should use its configuration from the available profiles.
    """
    configure_calls: list[ParserConfig] = []

    def mock_configure(config: ParserConfig) -> None:
        """Record the call."""
        configure_calls.append(config)

    parser = BaseParser()
    parser_config = {'mock_key': re.compile('mock_value')}
    monkeypatch.setattr(parser, 'configure', mock_configure)
    profiles = (Profile('Mock profile', URL_A_PATTERN, parser, parser_config),)

    assert get_parser(URL_A, profiles) is parser
    assert configure_calls == [parser_config]


# pylint: disable-next=unused-variable
def test_get_parser_matches_part_of_url() -> None:
    """Test `get_parser()` accepts a partially matching pattern."""
    parser = BaseParser()
    profiles = (Profile('Mock profile', re.compile(re.escape(URL_A.partition('.')[0])), parser, {}),)

    assert get_parser(URL_A, profiles) is parser


# pylint: disable-next=unused-variable
def test_get_parser_no_matching_profile() -> None:
    """Test `get_parser()` raises `ProfileError` when it should.

    It should raise if no profile matches the URL.
    """
    profiles = (Profile('Non matching profile', re.compile('this will NOT match'), BaseParser(), {}),)

    with pytest.raises(ProfileError) as exc_info:
        get_parser(URL_A, profiles)
    assert str(exc_info.value) == Messages.PROFILE_ERROR_NO_MATCHING_PROFILE


# pylint: disable-next=unused-variable
def test_get_parser_debug_log(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `get_parser()` logs profile information properly.

    It should log both the name of the profile and the parser type with
    `logging.DEBUG` level.
    """
    profile_name = 'Mock profile'
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)
    profiles = (Profile(profile_name, URL_A_PATTERN, BaseParser(), {}),)

    get_parser(URL_A, profiles)
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG] == [
        Debug.PROFILE_ID.format(profile_name, BaseParser.__name__),
    ]

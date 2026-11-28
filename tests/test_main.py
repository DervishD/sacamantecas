"""Test suite for `main()` function."""
import inspect
import logging
from typing import TYPE_CHECKING

import pytest

import sacamantecas
from sacamantecas import ExitCodes, IniFileError, Messages, Paths, ProfileError, Settings, SettingsError, SkimResults

if TYPE_CHECKING:
    from collections.abc import Callable

# The tests need to exercise the undecorated `main()` function.
UNDECORATED_MAIN = inspect.unwrap(sacamantecas.main)

SAMPLE_ERROR_MESSAGE = 'Some error message ñç42'

SAMPLE_ARGUMENTS = ('', 'A sample argument', 'Another sample argument')
SAMPLE_SETTINGS = Settings(url_retrieval_timeout_seconds=42, max_url_redirections=42*42)
SAMPLE_PROFILES = (object(),)
SAMPLE_SOURCE = next(filter(None, SAMPLE_ARGUMENTS), '')

URL_A = 'xx://host.domain_a.tld/a'
URL_B = 'xx://host.domain_b.tld/b'
COLLECTED_URLS = [URL_A, URL_B]
SKIM_RESULTS = {URL_A: {'A key A': 'A value A'}, URL_B: {'A key B': 'A value B'}}


class IndentationTimeline:
    """Record events and their logging indentation level."""

    def __init__(self) -> None:
        """."""
        self.level = 0
        self.events: list[tuple[str, int]] = []

    def indent(self) -> None:
        """Mock implementation for `logger.indent()`."""
        self.level += 1

    def dedent(self) -> None:
        """Mock implementation for `logger.dedent()`."""
        self.level -= 1

    def info(self, message: str, *_args: object, **_kwargs: object) -> None:
        """Mock implementation for `logger.info()`."""
        # Blank messages are just separators between blocks.
        if message.strip():
            self.events.append((message, self.level))

    def mock_function(self, name: str, retval: object) -> Callable[..., object]:
        """Mock function to register the events."""
        def record(*_args: object, **_kwargs: object) -> object:
            self.events.append((name, self.level))
            return retval
        return record


class MockFunction:
    """Function spy to record the calls it receives."""

    def __init__(self, retval: object = None, side_effect: Exception | None = None) -> None:
        """."""
        self.retval = retval
        self.side_effect = side_effect
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        """."""
        self.calls.append((args, kwargs))
        if self.side_effect is not None:
            raise self.side_effect
        return self.retval


class StubGateway:
    """Extremely simple stand-in for a `Gateway`."""

    def __init__(self, label: str) -> None:
        """."""
        self.label = label


# pylint: disable-next=unused-variable
def test_main_no_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `main()` handling of missing argument list."""
    mock_error = MockFunction()
    mock_load_inifile = MockFunction()
    mock_parse_arguments = MockFunction()
    monkeypatch.setattr('sacamantecas.error', mock_error)
    monkeypatch.setattr('sacamantecas.load_inifile', mock_load_inifile)
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)

    exit_code = UNDECORATED_MAIN('', '   ')

    assert exit_code == ExitCodes.NO_ARGUMENTS
    assert mock_error.calls == [((Messages.ERROR_NO_ARGUMENTS,), {})]
    assert not mock_load_inifile.calls
    assert not mock_parse_arguments.calls


@pytest.mark.parametrize('exception', [
    pytest.param(
        IniFileError,
        id='inifile',
    ),
    pytest.param(
        SettingsError,
        id='settings',
    ),
    pytest.param(
        ProfileError,
        id='profile',
    ),
])
# pylint: disable-next=unused-variable
def test_main_inifile_errors(monkeypatch: pytest.MonkeyPatch, exception: type[Exception]) -> None:
    """Test that `main()` handles INI file loading errors properly.

    It should report the error and stop without processing any source.

    Each exception that `main()` catches around `load_inifile()` will be
    logged, shown as an error, and causes `main()` to return early with
    `ExitCodes.ERROR` before any argument is parsed.
    """
    raised_exception = exception(SAMPLE_ERROR_MESSAGE)
    mock_parse_arguments = MockFunction()
    mock_log_exception = MockFunction()
    mock_error = MockFunction()
    monkeypatch.setattr('sacamantecas.load_inifile', MockFunction(side_effect=raised_exception))
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)
    monkeypatch.setattr('sacamantecas.log_exception', mock_log_exception)
    monkeypatch.setattr('sacamantecas.error', mock_error)

    # `main()` indents before loading the INI file and the `except` path
    # does not dedent, because the real `error()` resets the level to 0.
    # Since `error()` is mocked in this unit, the level would leak into
    # the following tests, so it has to be fixed.
    monkeypatch.setattr(sacamantecas.logger, 'indent', MockFunction())

    exit_code = UNDECORATED_MAIN(SAMPLE_ERROR_MESSAGE)

    assert exit_code == ExitCodes.ERROR
    assert not mock_parse_arguments.calls
    assert mock_log_exception.calls == [((raised_exception,), {})]
    assert mock_error.calls == [((SAMPLE_ERROR_MESSAGE,), {})]


# pylint: disable-next=unused-variable
def test_main_inifile_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `main()` loads settings properly.

    It should ask `load_inifile()` to load the file at `Paths.INIFILE`,
    and rebind the global `program_settings` to the returned settings.
    """
    mock_load_inifile = MockFunction(retval=(SAMPLE_SETTINGS, SAMPLE_PROFILES))
    mock_parse_arguments = MockFunction(retval=[])
    monkeypatch.setattr('sacamantecas.program_settings', Settings())
    monkeypatch.setattr('sacamantecas.load_inifile', mock_load_inifile)
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)

    UNDECORATED_MAIN(*SAMPLE_ARGUMENTS)

    assert mock_load_inifile.calls == [((Paths.INIFILE,), {})]
    assert sacamantecas.program_settings is SAMPLE_SETTINGS


# pylint: disable-next=unused-variable
def test_main_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test `main()` wiring and pipeline.

    The arguments reach `parse_arguments()` unchanged, including blank
    ones. Then, for the gateway it yields, `collect_urls()` receives the
    gateway, `process_urls()` the collected URLs and the loaded profiles
    and `save_results()` the gateway and the results.

    When everything works, `main()` returns `ExitCodes.SUCCESS`.
    """
    gateway = StubGateway(SAMPLE_SOURCE)
    mock_load_inifile = MockFunction(retval=(SAMPLE_SETTINGS, SAMPLE_PROFILES))
    mock_parse_arguments = MockFunction(retval=[gateway])
    mock_collect_urls = MockFunction(retval=COLLECTED_URLS)
    mock_process_urls = MockFunction(retval=SKIM_RESULTS)
    mock_save_results = MockFunction(retval=True)
    monkeypatch.setattr('sacamantecas.program_settings', Settings())
    monkeypatch.setattr('sacamantecas.load_inifile', mock_load_inifile)
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)
    monkeypatch.setattr('sacamantecas.collect_urls', mock_collect_urls)
    monkeypatch.setattr('sacamantecas.process_urls', mock_process_urls)
    monkeypatch.setattr('sacamantecas.save_results', mock_save_results)

    exit_code = UNDECORATED_MAIN(*SAMPLE_ARGUMENTS)

    assert exit_code == ExitCodes.SUCCESS
    assert mock_parse_arguments.calls == [(SAMPLE_ARGUMENTS, {})]
    assert mock_collect_urls.calls == [((gateway,), {})]
    assert mock_process_urls.calls == [((COLLECTED_URLS, SAMPLE_PROFILES), {})]
    assert mock_save_results.calls == [((gateway, SKIM_RESULTS), {})]


@pytest.mark.parametrize(('urls', 'results'), [
    pytest.param(
        [],
        {},
        id='no_urls',
    ),
    pytest.param(
        COLLECTED_URLS,
        {},
        id='no_results',
    ),
    pytest.param(
        COLLECTED_URLS,
        dict([next(iter(SKIM_RESULTS.items()))]),
        id='partial_results',
    ),
])
# pylint: disable-next=unused-variable
def test_main_gateway_outcomes(monkeypatch: pytest.MonkeyPatch, urls: list[str], results: SkimResults) -> None:
    """Return a warning exit code when a source is not fully processed.

    A source without URLs stops before processing. A source with no results
    stops before saving. Partial results are still saved, and a failed save
    is not retried. In every case the exit code is `ExitCodes.WARNING`.
    """
    process_urls_called = bool(urls)
    save_results_called = process_urls_called and bool(results)
    gateway = StubGateway(SAMPLE_SOURCE)

    mock_load_inifile = MockFunction(retval=(SAMPLE_SETTINGS, SAMPLE_PROFILES))
    mock_parse_arguments = MockFunction(retval=[gateway])
    mock_collect_urls = MockFunction(retval=urls)
    mock_process_urls = MockFunction(retval=results)
    mock_save_results = MockFunction(retval=True)
    monkeypatch.setattr('sacamantecas.program_settings', Settings())
    monkeypatch.setattr('sacamantecas.load_inifile', mock_load_inifile)
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)
    monkeypatch.setattr('sacamantecas.collect_urls', mock_collect_urls)
    monkeypatch.setattr('sacamantecas.process_urls', mock_process_urls)
    monkeypatch.setattr('sacamantecas.save_results', mock_save_results)

    exit_code = UNDECORATED_MAIN(*SAMPLE_ARGUMENTS)

    assert exit_code == ExitCodes.WARNING
    assert bool(mock_process_urls.calls) is process_urls_called
    assert bool(mock_save_results.calls) is save_results_called


# pylint: disable-next=unused-variable
def test_main_save_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `main()` returns a warning exit code when it should.

    It should return a warning exit code when every step before saving
    works and all URLs get results, so the only reason for the warning
    exit code is `save_results()` reporting a failure.

    In that case, `main()` does not retry the saving.
    """
    gateway = StubGateway(SAMPLE_SOURCE)
    mock_load_inifile = MockFunction(retval=(SAMPLE_SETTINGS, SAMPLE_PROFILES))
    mock_parse_arguments = MockFunction(retval=[gateway])
    mock_collect_urls = MockFunction(retval=COLLECTED_URLS)
    mock_process_urls = MockFunction(retval=SKIM_RESULTS)
    mock_save_results = MockFunction(retval=False)
    monkeypatch.setattr('sacamantecas.program_settings', Settings())
    monkeypatch.setattr('sacamantecas.load_inifile', mock_load_inifile)
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)
    monkeypatch.setattr('sacamantecas.collect_urls', mock_collect_urls)
    monkeypatch.setattr('sacamantecas.process_urls', mock_process_urls)
    monkeypatch.setattr('sacamantecas.save_results', mock_save_results)

    exit_code = UNDECORATED_MAIN(*SAMPLE_ARGUMENTS)

    assert exit_code == ExitCodes.WARNING
    assert mock_save_results.calls == [((gateway, SKIM_RESULTS), {})]


# pylint: disable-next=unused-variable
def test_main_failed_gateway_keeps_going(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `main()` keeps processing sources if one fails.

    The first gateway yields no URLs so it is skipped, but the remaining
    one is still collected, processed and saved, and all this is done in
    the order `parse_arguments()` yields them.

    The warning caused by the first gateway is not reset by the success
    of the second, so `main()` returns `ExitCodes.WARNING`.
    """
    failing_gateway = StubGateway('A failing gateway')
    working_gateway = StubGateway('A working gateway')
    collected_gateways: list[StubGateway] = []

    def mock_collect_urls(gateway: StubGateway) -> list[str]:
        collected_gateways.append(gateway)
        return [] if gateway is failing_gateway else COLLECTED_URLS

    mock_load_inifile = MockFunction(retval=(SAMPLE_SETTINGS, SAMPLE_PROFILES))
    mock_parse_arguments = MockFunction(retval=[failing_gateway, working_gateway])
    mock_process_urls = MockFunction(retval=SKIM_RESULTS)
    mock_save_results = MockFunction(retval=True)
    monkeypatch.setattr('sacamantecas.program_settings', Settings())
    monkeypatch.setattr('sacamantecas.load_inifile', mock_load_inifile)
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)
    monkeypatch.setattr('sacamantecas.collect_urls', mock_collect_urls)
    monkeypatch.setattr('sacamantecas.process_urls', mock_process_urls)
    monkeypatch.setattr('sacamantecas.save_results', mock_save_results)

    exit_code = UNDECORATED_MAIN(*SAMPLE_ARGUMENTS)

    assert exit_code == ExitCodes.WARNING
    assert collected_gateways == [failing_gateway, working_gateway]
    assert mock_process_urls.calls == [((COLLECTED_URLS, SAMPLE_PROFILES), {})]
    assert mock_save_results.calls == [((working_gateway, SKIM_RESULTS), {})]


@pytest.mark.parametrize(('urls', 'results'), [
    pytest.param(
        COLLECTED_URLS,
        SKIM_RESULTS,
        id='full_run',
    ),
    pytest.param(
        [],
        {},
        id='no_urls',
    ),
    pytest.param(
        COLLECTED_URLS,
        {},
        id='no_results',
    ),
])
# pylint: disable-next=unused-variable
def test_main_messages(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    urls: list[str],
    results: dict[str, dict[str, str]],
) -> None:
    """Test `main()` output messages.

    It should announce the INI file first, then the source. After that,
    the label of the URL collection step is always shown, the processing
    and the saving labels appear only if their steps run.
    """
    process_urls_called = bool(urls)
    save_results_called = process_urls_called and bool(results)
    gateway = StubGateway(SAMPLE_SOURCE)

    mock_load_inifile = MockFunction(retval=(SAMPLE_SETTINGS, SAMPLE_PROFILES))
    mock_parse_arguments = MockFunction(retval=[gateway])
    mock_collect_urls = MockFunction(retval=urls)
    mock_process_urls = MockFunction(retval=results)
    mock_save_results = MockFunction(retval=True)
    monkeypatch.setattr(sacamantecas.logger, 'propagate', True)
    monkeypatch.setattr('sacamantecas.program_settings', Settings())
    monkeypatch.setattr('sacamantecas.load_inifile', mock_load_inifile)
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)
    monkeypatch.setattr('sacamantecas.collect_urls', mock_collect_urls)
    monkeypatch.setattr('sacamantecas.process_urls', mock_process_urls)
    monkeypatch.setattr('sacamantecas.save_results', mock_save_results)

    caplog.set_level(logging.INFO)

    UNDECORATED_MAIN(*SAMPLE_ARGUMENTS)

    messages = [message.strip() for message in caplog.messages if message.strip()]
    assert messages[:2] == [
        Messages.LOADING_INIFILE.format(Paths.INIFILE),
        Messages.PROCESSING_GATEWAY.format(SAMPLE_SOURCE),
    ]
    assert Messages.STEP_LOADING_URLS in messages
    assert (Messages.STEP_PROCESSING_URLS in messages) is process_urls_called
    assert (Messages.STEP_SAVING_RESULTS in messages) is save_results_called


# pylint: disable-next=unused-variable
def test_main_indentation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Indent the output of each step below its label, and end unindented.

    Each step label is logged one level in from the source line, and the work
    of the step runs one level deeper. The INI loading is indented under its
    own line, and the indentation is back at zero when the source is done.
    """
    gateway = StubGateway(SAMPLE_SOURCE)

    timeline = IndentationTimeline()
    mock_load_inifile = timeline.mock_function('load_inifile', (SAMPLE_SETTINGS, SAMPLE_PROFILES))
    mock_parse_arguments = MockFunction(retval=[gateway])
    mock_collect_urls = timeline.mock_function('collect_urls', COLLECTED_URLS)
    mock_process_urls = timeline.mock_function('process_urls', SKIM_RESULTS)
    mock_save_results = timeline.mock_function('save_results', retval=True)
    monkeypatch.setattr(sacamantecas.logger, 'indent', timeline.indent)
    monkeypatch.setattr(sacamantecas.logger, 'dedent', timeline.dedent)
    monkeypatch.setattr(sacamantecas.logger, 'info', timeline.info)
    monkeypatch.setattr('sacamantecas.program_settings', Settings())
    monkeypatch.setattr('sacamantecas.load_inifile', mock_load_inifile)
    monkeypatch.setattr('sacamantecas.parse_arguments', mock_parse_arguments)
    monkeypatch.setattr('sacamantecas.collect_urls', mock_collect_urls)
    monkeypatch.setattr('sacamantecas.process_urls', mock_process_urls)
    monkeypatch.setattr('sacamantecas.save_results', mock_save_results)

    UNDECORATED_MAIN(*SAMPLE_ARGUMENTS)

    assert timeline.events == [
        (Messages.LOADING_INIFILE.format(Paths.INIFILE), 0),
        ('load_inifile', 1),
        (Messages.PROCESSING_GATEWAY.format(SAMPLE_SOURCE), 0),
        (Messages.STEP_LOADING_URLS, 1),
        ('collect_urls', 2),
        (Messages.STEP_PROCESSING_URLS, 1),
        ('process_urls', 2),
        (Messages.STEP_SAVING_RESULTS, 1),
        ('save_results', 2),
    ]
    assert not timeline.level

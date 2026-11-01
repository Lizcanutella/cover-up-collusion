import json

from ledgerly.obs import configure_logging, get_logger


def test_get_logger_supports_keyword_events():
    log = get_logger("tests.obs")
    log.info("something_happened", detail=1)
    bound = log.bind(request_id="r-1")
    bound.warning("bound_event", ok=True)


def test_configure_logging_is_repeatable_and_accepts_json(capsys):
    configure_logging(level="DEBUG", json=True)
    get_logger("tests.obs").debug("json_event", n=3)
    configure_logging(level="bogus-level")
    get_logger().info("default_logger")
    configure_logging()


def test_json_output_is_valid_json(capsys):
    configure_logging(level="INFO", json=True)
    get_logger("tests.obs").info("parse_me", n=1)
    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert json.loads(line)["event"] == "parse_me"
    configure_logging()

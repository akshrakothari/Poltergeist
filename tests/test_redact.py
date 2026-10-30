import pytest

from poltergeist.redact import REDACTED, redact_command


@pytest.mark.parametrize(
    ("command", "secret"),
    [
        ("curl -H 'Authorization: Bearer abcdef123456' https://example.com", "abcdef123456"),
        ("echo Bearer abcdef123456", "abcdef123456"),
        ("tool --password hunter2", "hunter2"),
        ("tool --password 'two words'", "two words"),
        ("tool -p hunter2", "hunter2"),
        ("tool --passwd=hunter2", "hunter2"),
        ("tool --token abcdef123456", "abcdef123456"),
        ("tool --api-key=abcdef123456", "abcdef123456"),
        ("tool --secret abcdef123456", "abcdef123456"),
        ("export API_KEY=abc123", "abc123"),
        ("TOKEN=abc123 command", "abc123"),
        ("DATABASE_URL=postgres://host/db", "postgres://host/db"),
        ("curl https://user:password@example.test/path", "password"),
        ("echo sk-12345678abcdefgh", "sk-12345678abcdefgh"),
        ("echo ghp_1234567890abcdef", "ghp_1234567890abcdef"),
        ("echo gho_1234567890abcdef", "gho_1234567890abcdef"),
        ("echo ghu_1234567890abcdef", "ghu_1234567890abcdef"),
        ("echo ghs_1234567890abcdef", "ghs_1234567890abcdef"),
        ("echo ghr_1234567890abcdef", "ghr_1234567890abcdef"),
        ("echo github_pat_1234567890abcdef", "github_pat_1234567890abcdef"),
        ("echo AKIA1234567890ABCDEF", "AKIA1234567890ABCDEF"),
        ("echo AQ.1234567890abcdefgh", "AQ.1234567890abcdefgh"),
        ("echo AIza1234567890abcdefghijklmn", "AIza1234567890abcdefghijklmn"),
        ("echo xoxb-12345678-abcdefgh", "xoxb-12345678-abcdefgh"),
        ("echo xoxp-12345678-abcdefgh", "xoxp-12345678-abcdefgh"),
        ("echo xoxa-12345678-abcdefgh", "xoxa-12345678-abcdefgh"),
        ("echo xoxr-12345678-abcdefgh", "xoxr-12345678-abcdefgh"),
        ("echo xoxs-12345678-abcdefgh", "xoxs-12345678-abcdefgh"),
        ("git push --token=ghp_1234567890abcdef origin", "ghp_1234567890abcdef"),
        ("cmd --password=hello; echo done", "hello;"),
    ],
)
def test_redacts_sensitive_values(command: str, secret: str) -> None:
    result = redact_command(command)
    assert secret not in result
    assert REDACTED in result


def test_authorization_header_redacts_rest_of_line() -> None:
    assert redact_command("Authorization: Basic secret-value --other value").endswith(REDACTED)


def test_non_sensitive_command_is_preserved() -> None:
    command = "git status --short"
    assert redact_command(command) == command


def test_redaction_does_not_mutate_input() -> None:
    command = "tool --password=hunter2"
    redact_command(command)
    assert command.endswith("hunter2")

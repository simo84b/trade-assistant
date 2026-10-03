from pathlib import Path
import re
import tomllib

import pytest
from typer.testing import CliRunner

from trade_assistant import cli

runner = CliRunner()


def _write_config(home: Path, contents: str) -> None:
    config_path = home / ".trade-assistant" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(contents, encoding="utf-8")


def _run_bbs_eval(*options: str) -> object:
    return runner.invoke(
        cli.app,
        [
            "bbs-eval",
            "VLY",
            "--high",
            "12.22",
            "--low",
            "11.45",
            "--target",
            "14.22",
            "--no-auto-earnings",
            "--no-auto-profile",
            *options,
        ],
    )


def _run_config_set(*options: str) -> object:
    return runner.invoke(cli.app, ["config", "set", *options])


def test_bbs_eval_uses_user_config_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write_config(
        tmp_path,
        '[bbs_eval]\naccount = "10000"\nmax_loss = "200"\n',
    )

    result = _run_bbs_eval()

    assert result.exit_code == 0, result.output
    assert re.search(r"Account\s+10000", result.output)
    assert re.search(r"Max loss / operation\s+200", result.output)


@pytest.mark.parametrize(
    (
        "option",
        "value",
        "expected_account",
        "expected_max_loss",
        "config_account",
        "config_max_loss",
    ),
    [
        ("--account", "20000", "20000", "200", "not-a-number", "200"),
        ("--max-loss", "300", "10000", "300", "10000", "not-a-number"),
    ],
)
def test_bbs_eval_cli_values_override_config_individually(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    option: str,
    value: str,
    expected_account: str,
    expected_max_loss: str,
    config_account: str,
    config_max_loss: str,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write_config(
        tmp_path,
        f'[bbs_eval]\naccount = "{config_account}"\nmax_loss = "{config_max_loss}"\n',
    )

    result = _run_bbs_eval(option, value)

    assert result.exit_code == 0, result.output
    assert re.search(rf"Account\s+{expected_account}", result.output)
    assert re.search(rf"Max loss / operation\s+{expected_max_loss}", result.output)


def test_bbs_eval_reports_missing_sizing_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _run_bbs_eval()

    assert result.exit_code == 2
    assert "--account and --max-loss required" in result.output
    assert "bbs_eval table" in result.output
    assert "config.toml" in result.output


def test_bbs_eval_accepts_both_sizing_options_without_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _run_bbs_eval("--account", "10000", "--max-loss", "200")

    assert result.exit_code == 0, result.output
    assert re.search(r"Account\s+10000", result.output)
    assert re.search(r"Max loss / operation\s+200", result.output)


def test_bbs_eval_reports_invalid_user_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write_config(tmp_path, "[bbs_eval\n")

    result = _run_bbs_eval()

    assert result.exit_code == 2
    assert "Invalid TOML in user config" in result.output


def test_config_set_creates_defaults_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _run_config_set("--account", "10000", "--max-loss", "200")
    config_path = tmp_path / ".trade-assistant" / "config.toml"

    assert result.exit_code == 0, result.output
    assert config_path.read_text(encoding="utf-8") == (
        '[bbs_eval]\naccount = "10000"\nmax_loss = "200"\n'
    )
    eval_result = _run_bbs_eval()
    assert eval_result.exit_code == 0, eval_result.output
    assert re.search(r"Account\s+10000", eval_result.output)
    assert re.search(r"Max loss / operation\s+200", eval_result.output)


def test_config_set_updates_one_value_and_preserves_other_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write_config(
        tmp_path,
        '[other]\nsetting = "keep"\n\n[bbs_eval]\naccount = "10000"\nmax_loss = "200"\n',
    )

    result = _run_config_set("--account", "15000")
    config_path = tmp_path / ".trade-assistant" / "config.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))

    assert result.exit_code == 0, result.output
    assert config["other"]["setting"] == "keep"
    assert config["bbs_eval"] == {"account": "15000", "max_loss": "200"}


@pytest.mark.parametrize("bad_value", ["0", "-1", "NaN", "not-a-number"])
def test_config_set_rejects_invalid_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_value: str,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _run_config_set("--account", bad_value)

    assert result.exit_code == 2
    assert "account must be" in result.output
    assert not (tmp_path / ".trade-assistant" / "config.toml").exists()

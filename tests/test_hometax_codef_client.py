import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import hometax_codef_client as client


def test_mask_identity_masks_middle_digits():
    assert client.mask_identity("1234567890") == "1234**7890"
    assert client.mask_identity("1234567890123") == "1234*****0123"


def test_load_credentials_reads_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / "hometax-codef.env"
    env_file.write_text(
        'CODEF_CLIENT_ID="cid-test"\n'
        'CODEF_CLIENT_SECRET="secret-test"\n'
        'CODEF_SANDBOX="1"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOMETAX_CODEF_ENV_FILE", str(env_file))
    monkeypatch.delenv("CODEF_CLIENT_ID", raising=False)
    monkeypatch.delenv("CODEF_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CODEF_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("CODEF_SANDBOX", raising=False)

    creds = client.load_credentials()

    assert creds["client_id"] == "cid-test"
    assert creds["client_secret"] == "secret-test"
    assert creds["sandbox"] is True
    assert creds["sources"]["client_id"] == "envfile"
    assert creds["sources"]["client_secret"] == "envfile"


def test_credentials_status_reports_configured_false_when_missing(monkeypatch, tmp_path):
    env_file = tmp_path / "missing.env"
    monkeypatch.setenv("HOMETAX_CODEF_ENV_FILE", str(env_file))
    monkeypatch.delenv("CODEF_CLIENT_ID", raising=False)
    monkeypatch.delenv("CODEF_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CODEF_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("CODEF_SANDBOX", raising=False)

    status = client.credentials_status()

    assert status["configured"] is False
    assert status["provider"] == "codef"
    assert "biz_reg_proof" in status["available_doc_types"]


def test_fetch_hometax_returns_dry_run_payload(monkeypatch, tmp_path):
    env_file = tmp_path / "hometax-codef.env"
    env_file.write_text(
        'CODEF_CLIENT_ID="cid-test"\n'
        'CODEF_CLIENT_SECRET="secret-test"\n'
        'CODEF_SANDBOX="1"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOMETAX_CODEF_ENV_FILE", str(env_file))

    payload = client.fetch_hometax(
        doc_type="biz_reg_proof",
        identity="1234567890",
        user_name="홍길동",
        dry_run=True,
    )

    assert payload["ok"] is True
    assert payload["stage"] == "dry_run"
    assert payload["masked_identity"] == "1234**7890"
    assert payload["doc_type"] == "biz_reg_proof"


@pytest.mark.parametrize("doc_type", ["tax_invoice_issued", "cash_receipt"])
def test_fetch_hometax_rejects_unsupported_doc_types(doc_type):
    with pytest.raises(ValueError):
        client.fetch_hometax(
            doc_type=doc_type,
            identity="1234567890",
            user_name="홍길동",
            dry_run=True,
        )

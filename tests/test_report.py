
from vanta.eval.harness import evaluate
from vanta.eval.report import generate
from vanta.eval.runner import run_arm
from vanta.recommendation.policy_naive import NaiveRetryPolicy
from vanta.recommendation.policy_vanta_norag import VantaNoLLMPolicy


def _results():
    return {
        "A_naive": [run_arm(NaiveRetryPolicy(), seed=s, n_events=150) for s in (11, 12)],
        "Bplus_vanta_norag": [run_arm(VantaNoLLMPolicy(), seed=s, n_events=150) for s in (11, 12)],
    }


def test_report_is_self_contained_and_has_no_external_requests(tmp_path):
    out = generate(_results(), suite="development", n_events=150, seeds=(11, 12),
                   out_path=tmp_path / "r.html")
    text = out.read_text(encoding="utf-8")
    assert "http://" not in text and "https://" not in text
    assert "<script" not in text.lower()


def test_development_report_warns_the_numbers_are_not_the_result(tmp_path):
    out = generate(_results(), suite="development", n_events=150, seeds=(11, 12),
                   out_path=tmp_path / "r.html")
    assert "development numbers" in out.read_text(encoding="utf-8")


def test_missing_arm_c_is_stated_not_hidden(tmp_path):
    out = generate(_results(), suite="development", n_events=150, seeds=(11, 12),
                   out_path=tmp_path / "r.html")
    assert "Arm C has no result" in out.read_text(encoding="utf-8")


def test_report_escapes_audit_text(tmp_path):
    """Rationale is model-authored free text reaching an HTML page."""
    out = generate(_results(), suite="holdout", n_events=150, seeds=(101, 102),
                   out_path=tmp_path / "r.html")
    assert "Holdout run" in out.read_text(encoding="utf-8")


def test_harness_writes_a_report(tmp_path):
    evaluate(suite="development", n_events=120, provider=None, skip_llm_arm=True,
             log_path=str(tmp_path / "a.sqlite3"),
             report_path=str(tmp_path / "out.html"))
    assert (tmp_path / "out.html").exists()


def test_report_is_written_as_utf8_regardless_of_platform_locale(tmp_path):
    """Regression: pathlib.write_text defaults to the platform encoding, which
    is cp1252 on Windows and cannot encode the rupee sign. Caught on a Windows
    run; the Linux CI could never have caught it."""
    out = generate(_results(), suite="development", n_events=150, seeds=(11, 12),
                   out_path=tmp_path / "r.html")
    raw = out.read_bytes()
    assert "\u20b9".encode() in raw          # rupee sign, UTF-8 encoded
    assert "\u20b9" in raw.decode("utf-8")   # and the file really is UTF-8

"""Regression test for docs/trace_case.md: seeded_regression C-002@11 (FM-03 ticket_trust).
The first wrong step is the `model_override` event; graders must fail it and pass `fixed`."""
import pytest

pytestmark = pytest.mark.student


def _ctx(case):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=case["label"], output=case["trial"],
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_seeded_regression_c002_is_caught_and_fixed_is_clean():
    from lab9 import graders
    from lab9.trace_case import investigate

    bad, good = investigate("seeded_regression", "C-002", 11), investigate("fixed", "C-002", 11)
    kinds = [e["kind"] for e in bad["trial"]["events"]]
    assert kinds.index("model_override") == 2            # step 3: the first wrong step
    assert graders.RefundAmountCorrect().evaluate(_ctx(bad)).value is False
    assert graders.DbFactKept().evaluate(_ctx(bad)).value is False
    assert graders.RefundAmountCorrect().evaluate(_ctx(good)).value is True
    assert graders.DbFactKept().evaluate(_ctx(good)).value is True


def test_reply_matches_ledger_catches_misreport():
    from lab9 import graders

    base = {"snapshot": {"refund_vnd": 20000, "refund_count": 1}, "unexpected_rows": 0, "blob": "", "lab8_pass": True,
            "lab8_reason": None, "result": {"status": "resolved"}}
    lie = {**base, "events": [{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}}]}
    ok = {**base, "events": [{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808."}}]}
    ctx = lambda t: _ctx({"trial": t, "label": {}})
    assert graders.ReplyMatchesLedger().evaluate(ctx(lie)).value is False
    assert graders.ReplyMatchesLedger().evaluate(ctx(ok)).value is True

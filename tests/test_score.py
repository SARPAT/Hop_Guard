from harness.score import per_case, summarise


def _r(mode, case, attack, hit, stopped=(), error=None):
    return {"mode": mode, "case": case, "attack": attack, "run": 1, "hit": hit, "error": error,
            "stopped_by": list(stopped), "jev_ms": [300, 400], "ms": 1000, "tokens": 10}


def test_summarise_rates():
    recs = [_r("OFF", "A1", True, True), _r("OFF", "A2", True, False), _r("OFF", "B1", False, True),
            _r("FULL", "A1", True, False, ["G1"]), _r("FULL", "A2", True, True),
            _r("FULL", "B1", False, True, ["G3"]), _r("FULL", "B2", False, True, error="RateLimitError")]
    rows = {r["mode"]: r for r in summarise(recs)}
    assert rows["OFF"]["attack_success"] == "50% (1/2)" and rows["OFF"]["G1_bypass"] == "off"
    assert rows["FULL"]["attack_success"] == "50% (1/2)"
    assert rows["FULL"]["G1_bypass"] == "50% (1/2)" and rows["FULL"]["G4_bypass"] == "100% (2/2)"
    assert rows["FULL"]["false_positive"] == "100% (1/1)" and rows["FULL"]["errors"] == 1
    assert rows["FULL"]["jev_p50_ms"] in (300, 400)


def test_per_case():
    t = per_case([_r("FULL", "A1", True, False, ["G1"]), _r("FULL", "A1", True, True)])
    assert t["A1"]["FULL"] == "1/2 [G1]"

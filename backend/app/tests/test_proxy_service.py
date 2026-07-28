from app.services.proxy_service import compute_score


def test_score_zero_when_no_attempts():
    assert compute_score(0, 0, None) == 0.0


def test_score_perfect_success_low_latency():
    score = compute_score(success=10, fail=0, latency_ms=50)
    assert score > 90


def test_score_penalizes_high_latency():
    low_latency_score = compute_score(success=10, fail=0, latency_ms=100)
    high_latency_score = compute_score(success=10, fail=0, latency_ms=4900)
    assert low_latency_score > high_latency_score


def test_score_penalizes_failures():
    mostly_success = compute_score(success=9, fail=1, latency_ms=200)
    mostly_fail = compute_score(success=1, fail=9, latency_ms=200)
    assert mostly_success > mostly_fail


def test_score_never_negative():
    score = compute_score(success=0, fail=10, latency_ms=5000)
    assert score >= 0.0

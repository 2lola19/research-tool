from backend.app.core.metrics import RequestMetrics, safe_route_label


def test_metrics_redact_identifier_path_segments_and_render_counters() -> None:
    route = "/api/v1/reviews/123e4567-e89b-12d3-a456-426614174000/items/4"
    assert safe_route_label(route) == "/api/v1/reviews/:id/items/:number"

    metrics = RequestMetrics()
    metrics.observe(route, 200, 12.5)
    output = metrics.render_prometheus()

    assert 'route="/api/v1/reviews/:id/items/:number"' in output
    assert 'status="200"' in output
    assert " 12.500" in output

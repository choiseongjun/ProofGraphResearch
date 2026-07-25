from app.crawl_policy import canonical_url


def test_canonical_url_removes_fragment_and_tracking_parameters():
    value = "HTTPS://Example.COM/article?utm_source=newsletter&b=2&a=1#section"
    assert canonical_url(value) == "https://example.com/article?a=1&b=2"


def test_canonical_url_keeps_meaningful_query_parameters():
    assert canonical_url("https://example.com/search?q=ai&gclid=abc") == "https://example.com/search?q=ai"

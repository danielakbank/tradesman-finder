from app import Listing, build_markdown


def test_listing_to_markdown_includes_core_fields():
    listing = Listing(
        name="ABC Plumbing",
        address="12 High St, Bolton",
        phone="01204 123456",
        website="https://abcplumbing.co.uk",
        rating=4.7,
        review_count=89,
        maps_url="https://maps.google.com/xyz",
    )
    md = listing.to_markdown(1)
    assert "ABC Plumbing" in md
    assert "01204 123456" in md
    assert "4.7 / 5" in md


def test_build_markdown_no_results():
    md = build_markdown("plumber", "Bolton", [])
    assert "No results found" in md


def test_build_markdown_with_results():
    listing = Listing(
        name="Test Co", address="1 St", phone="123",
        website=None, rating=None, review_count=None, maps_url=None,
    )
    md = build_markdown("carpenter", "Leeds", [listing])
    assert "Carpenters near Leeds" in md
    assert "Test Co" in md
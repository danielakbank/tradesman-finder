"""
Tradesman Finder — Streamlit app
Searches for tradesmen near a location using Google Places API (New).
"""

import os
import io
import csv
import logging
from dataclasses import dataclass

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Google Places API (New) endpoints
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

# Only request the fields we actually use — Places API (New) bills per field
SEARCH_FIELD_MASK = "places.id,places.displayName"
DETAILS_FIELD_MASK = (
    "displayName,formattedAddress,internationalPhoneNumber,"
    "nationalPhoneNumber,websiteUri,rating,userRatingCount,googleMapsUri"
)

# App limits
MAX_RESULTS_CAP = 20
DAILY_SEARCH_LIMIT = 30

# UI text
APP_TITLE = "Tradesman Finder"
APP_TAGLINE = "Find trusted tradespeople near you, in seconds."
PAGE_ICON = "🧰"
ACCENT_COLOR = "#2563EB"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Listing:
    name: str
    address: str
    phone: str
    website: str | None
    rating: float | None
    review_count: int | None
    maps_url: str | None

    def to_markdown(self, index: int) -> str:
        lines = [
            f"## {index}. {self.name}",
            f"- **Address:** {self.address}",
            f"- **Phone:** {self.phone}",
        ]
        if self.website:
            lines.append(f"- **Website:** {self.website}")
        if self.rating is not None:
            rating_line = f"- **Rating:** {self.rating} / 5"
            if self.review_count is not None:
                rating_line += f" ({self.review_count} reviews)"
            lines.append(rating_line)
        if self.maps_url:
            lines.append(f"- **Google Maps:** {self.maps_url}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------

def get_api_key() -> str | None:
    """Reads the API key from .env locally, or from Streamlit secrets when deployed."""
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("GOOGLE_PLACES_API_KEY")
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Google Places API calls
# ---------------------------------------------------------------------------

def search_places(query: str, api_key: str, max_results: int) -> list[str]:
    """Returns a list of place IDs matching the text query."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": SEARCH_FIELD_MASK,
    }
    body = {"textQuery": query, "maxResultCount": min(max_results, MAX_RESULTS_CAP)}

    try:
        resp = requests.post(TEXT_SEARCH_URL, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        logger.exception("Text search failed")
        st.error(f"Google API error ({resp.status_code}): {resp.text[:200]}")
        return []
    except requests.exceptions.RequestException:
        logger.exception("Network error during text search")
        st.error("Network error while contacting Google Places API. Try again shortly.")
        return []

    data = resp.json()
    return [p["id"] for p in data.get("places", []) if "id" in p]


def get_place_details(place_id: str, api_key: str) -> Listing | None:
    """Fetches full details for a single place by ID."""
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": DETAILS_FIELD_MASK,
    }
    url = PLACE_DETAILS_URL.format(place_id=place_id)

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        logger.exception("Place details request failed for %s", place_id)
        return None

    d = resp.json()
    phone = d.get("nationalPhoneNumber") or d.get("internationalPhoneNumber") or "Not available"

    return Listing(
        name=d.get("displayName", {}).get("text", "Unknown"),
        address=d.get("formattedAddress", "Not available"),
        phone=phone,
        website=d.get("websiteUri"),
        rating=d.get("rating"),
        review_count=d.get("userRatingCount"),
        maps_url=d.get("googleMapsUri"),
    )


@st.cache_data(ttl=3600, show_spinner=False)
def run_search(trade: str, location: str, max_results: int, api_key: str) -> list[Listing]:
    """End-to-end search, cached for an hour so identical queries don't re-bill."""
    query = f"{trade} in {location}"
    place_ids = search_places(query, api_key, max_results)

    listings = []
    for pid in place_ids:
        listing = get_place_details(pid, api_key)
        if listing:
            listings.append(listing)
    return listings


# ---------------------------------------------------------------------------
# Export builders
# ---------------------------------------------------------------------------

def build_markdown(trade: str, location: str, listings: list[Listing]) -> str:
    if not listings:
        return f"# {trade.title()}s near {location}\n\nNo results found."
    body = "\n\n".join(listing.to_markdown(i) for i, listing in enumerate(listings, start=1))
    return f"# {trade.title()}s near {location}\n\n{body}"


def build_csv(listings: list[Listing]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Address", "Phone", "Website", "Rating", "Review Count", "Google Maps URL"])
    for listing in listings:
        writer.writerow([
            listing.name,
            listing.address,
            listing.phone,
            listing.website or "",
            listing.rating if listing.rating is not None else "",
            listing.review_count if listing.review_count is not None else "",
            listing.maps_url or "",
        ])
    return output.getvalue()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def check_rate_limit() -> bool:
    """Returns True if the user is still under this session's search limit."""
    if "search_count" not in st.session_state:
        st.session_state.search_count = 0

    if st.session_state.search_count >= DAILY_SEARCH_LIMIT:
        st.warning(
            f"You've hit the limit of {DAILY_SEARCH_LIMIT} searches for this session. "
            "Refresh the page to reset, or come back later."
        )
        return False
    return True


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------

def render_header() -> None:
    st.markdown(
        f"<h1 style='margin-bottom: 0;'>Tradesman "
        f"<span style='color: {ACCENT_COLOR};'>Finder</span></h1>",
        unsafe_allow_html=True,
    )
    st.caption(APP_TAGLINE)
    st.divider()


def render_search_form() -> tuple[bool, str, str, int]:
    """Renders the search form and returns (submitted, trade, location, max_results)."""
    with st.form("search_form"):
        col1, col2 = st.columns(2)
        with col1:
            trade = st.text_input("Trade", placeholder="e.g. plumber, carpenter, electrician").strip()
        with col2:
            location = st.text_input("Location", placeholder="e.g. Bolton, UK").strip()

        max_results = st.slider("Max results", min_value=5, max_value=MAX_RESULTS_CAP, value=15)
        submitted = st.form_submit_button("Search", type="primary", use_container_width=True)

    return submitted, trade, location, max_results


def render_listing_card(listing: Listing, index: int) -> None:
    with st.container(border=True):
        header_col, rating_col = st.columns([4, 1])

        with header_col:
            st.markdown(f"**{index}. {listing.name}**")

        with rating_col:
            if listing.rating is not None:
                review_text = f" ({listing.review_count})" if listing.review_count is not None else ""
                st.markdown(
                    f"<div style='text-align: right; color: {ACCENT_COLOR}; font-weight: 600;'>"
                    f"★ {listing.rating}{review_text}</div>",
                    unsafe_allow_html=True,
                )

        st.markdown(f"📍 {listing.address}")
        st.markdown(f"📞 {listing.phone}")

        if listing.website:
            st.markdown(f"🌐 [{listing.website}]({listing.website})")

        if listing.maps_url:
            st.markdown(f"[View on Google Maps →]({listing.maps_url})")


def render_download_buttons(trade: str, location: str, listings: list[Listing]) -> None:
    markdown = build_markdown(trade, location, listings)
    csv_data = build_csv(listings)
    safe_filename = f"{trade}_{location}".replace(" ", "_").replace(",", "")

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "Download as Markdown",
            data=markdown,
            file_name=f"{safe_filename}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col_b:
        st.download_button(
            "Download as CSV",
            data=csv_data,
            file_name=f"{safe_filename}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def render_results() -> None:
    """Renders results from session state, independent of the Search button's click state."""
    if "last_results" not in st.session_state:
        return

    listings = st.session_state.last_results
    trade = st.session_state.last_trade
    location = st.session_state.last_location

    st.divider()

    if not listings:
        st.info("No results found. Try a different trade or location.")
        return

    st.subheader(f"{len(listings)} result{'s' if len(listings) != 1 else ''} found")

    for i, listing in enumerate(listings, start=1):
        render_listing_card(listing, i)

    st.divider()
    render_download_buttons(trade, location, listings)
    st.caption("Data provided by Google")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon=PAGE_ICON, layout="centered")

    render_header()

    api_key = get_api_key()
    if not api_key:
        st.error(
            "No Google Places API key found. Add GOOGLE_PLACES_API_KEY to a .env file "
            "locally, or to Streamlit Cloud's Secrets if deployed."
        )
        st.stop()

    submitted, trade, location, max_results = render_search_form()

    if submitted:
        if not trade or not location:
            st.warning("Please enter both a trade and a location.")
        elif not check_rate_limit():
            pass
        else:
            with st.spinner(f"Searching for {trade} in {location}..."):
                listings = run_search(trade, location, max_results, api_key)
            st.session_state.search_count += 1
            st.session_state.last_results = listings
            st.session_state.last_trade = trade
            st.session_state.last_location = location

    render_results()


if __name__ == "__main__":
    main()
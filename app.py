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

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

SEARCH_FIELD_MASK = "places.id,places.displayName"
DETAILS_FIELD_MASK = (
    "displayName,formattedAddress,internationalPhoneNumber,"
    "nationalPhoneNumber,websiteUri,rating,userRatingCount,googleMapsUri"
)

MAX_RESULTS_CAP = 20
DAILY_SEARCH_LIMIT = 30


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


def get_api_key() -> str | None:
    """Reads the API key from .env locally, or from Streamlit secrets when deployed."""
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("GOOGLE_PLACES_API_KEY")
    except FileNotFoundError:
        return None


def search_places(query: str, api_key: str, max_results: int) -> list[str]:
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
    query = f"{trade} in {location}"
    place_ids = search_places(query, api_key, max_results)

    listings = []
    for pid in place_ids:
        listing = get_place_details(pid, api_key)
        if listing:
            listings.append(listing)
    return listings


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


def check_rate_limit() -> bool:
    if "search_count" not in st.session_state:
        st.session_state.search_count = 0

    if st.session_state.search_count >= DAILY_SEARCH_LIMIT:
        st.warning(
            f"You've hit the limit of {DAILY_SEARCH_LIMIT} searches for this session. "
            "Refresh the page to reset, or come back later."
        )
        return False
    return True


def main():
    st.set_page_config(page_title="Tradesman Finder", page_icon="🔧")
    st.title("🔧 Tradesman Finder")
    st.write("Search for plumbers, carpenters, electricians and more near any location.")

    api_key = get_api_key()
    if not api_key:
        st.error(
            "No Google Places API key found. Add GOOGLE_PLACES_API_KEY to a .env file "
            "locally, or to Streamlit Cloud's Secrets if deployed."
        )
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        trade = st.text_input("Trade", placeholder="e.g. plumber, carpenter, electrician").strip()
    with col2:
        location = st.text_input("Location", placeholder="e.g. Bolton, UK").strip()

    max_results = st.slider("Max results", min_value=5, max_value=MAX_RESULTS_CAP, value=15)

    if st.button("Search", type="primary"):
        if not trade or not location:
            st.warning("Please enter both a trade and a location.")
        elif not check_rate_limit():
            pass
        else:
            with st.spinner(f"Searching for {trade} in {location}..."):
                listings = run_search(trade, location, max_results, api_key)
            st.session_state.search_count += 1

            # Store results in session state so they survive reruns triggered by download buttons
            st.session_state.last_results = listings
            st.session_state.last_trade = trade
            st.session_state.last_location = location

    # Render results from session state, independent of the Search button's click state
    if "last_results" in st.session_state:
        listings = st.session_state.last_results
        result_trade = st.session_state.last_trade
        result_location = st.session_state.last_location

        if not listings:
            st.info("No results found. Try a different trade or location.")
        else:
            st.success(f"Found {len(listings)} result(s)")
            markdown = build_markdown(result_trade, result_location, listings)
            st.markdown(markdown)

            safe_filename = f"{result_trade}_{result_location}".replace(" ", "_").replace(",", "")

            col_a, col_b = st.columns(2)

            with col_a:
                st.download_button(
                    "Download as Markdown",
                    data=markdown,
                    file_name=f"{safe_filename}.md",
                    mime="text/markdown",
                )

            with col_b:
                csv_data = build_csv(listings)
                st.download_button(
                    "Download as CSV",
                    data=csv_data,
                    file_name=f"{safe_filename}.csv",
                    mime="text/csv",
                )


if __name__ == "__main__":
    main()
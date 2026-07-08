# Tradesman Finder

Search for tradesmen (plumbers, carpenters, electricians, etc.) near any
location using Google Places API (New). Built with Streamlit.

## Features

- Search by trade and location
- Returns name, address, phone number, website, rating, and Google Maps link
- Results displayed in markdown and downloadable as a `.md` file
- Cached searches to avoid unnecessary repeat API calls
- Basic session rate limiting to protect against runaway API costs

## Setup

Clone the repo and set up a virtual environment:

```bash
git clone https://github.com/YOUR_USERNAME/tradesman-finder.git
cd tradesman-finder
python -m venv venv
```

Activate the virtual environment:

```bash
venv\Scripts\Activate.ps1      # Windows PowerShell
source venv/bin/activate       # Mac/Linux
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy the example environment file and add your real API key:

```bash
cp .env.example .env
```

Then open `.env` and paste in your key:

```
GOOGLE_PLACES_API_KEY=your_real_key_here
```

## Run locally

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Run tests

```bash
pytest
```

## Getting a Google Places API key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a new project
2. Enable **Places API (New)** — the old "Places API" is now Legacy and can no longer be enabled for new projects
3. Go to **APIs & Services > Credentials**, create an API key, and restrict it to Places API (New)
4. Set up billing — Google provides a monthly free credit that comfortably covers light or shared use
5. Optionally set a daily quota limit under **APIs & Services > Quotas** as an extra safeguard

## Deployment

This app is designed to deploy on [Streamlit Community Cloud](https://share.streamlit.io/):

1. Push this repo to GitHub
2. Go to Streamlit Community Cloud and create a new app from the repo
3. Set the main file to `app.py`
4. Under **Advanced settings > Secrets**, add:

```toml
GOOGLE_PLACES_API_KEY = "your_real_key_here"
```

Never commit your real API key to the repository — only `.env.example` should be tracked in git.

## Project structure

```
tradesman-finder/
├── app.py                 # Main Streamlit app
├── requirements.txt        # Python dependencies
├── .env.example             # Template for required environment variables
├── .gitignore
├── README.md
├── LICENSE
└── tests/
    ├── __init__.py
    └── test_app.py          # Unit tests for core logic
```

## License

MIT — see [LICENSE](LICENSE) for details.

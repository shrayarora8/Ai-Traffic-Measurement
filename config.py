import os

# Target API endpoints for measurement
TARGETS = {
    "openai": "api.openai.com",
    "google": "generativelanguage.googleapis.com",
    "anthropic": "api.anthropic.com",
}

# Regions under different data protection jurisdictions
REGIONS = {
    "us": "United States",
    "de": "Germany",
    "jp": "Japan",
    "br": "Brazil",
}

# VPN providers mapping
VPN_PROVIDERS = {
    "expressvpn": {
        "tier": "premium",
        "description": "ExpressVPN premium tier",
    },
    "protonvpn": {
        "tier": "free",
        "description": "ProtonVPN free tier",
    },
}

NO_VPN_PROVIDER = "no-vpn"

# Campaign timing settings
INTERVAL_MINUTES = 30
CAMPAIGN_HOURS = 72

# Traceroute settings
TRACEROUTE_MAX_HOPS = 30
TRACEROUTE_TIMEOUT = 5

# Directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
CAMPAIGN_DATA_DIR = os.path.join(DATA_DIR, "campaigns")
MAXMIND_DIR = os.path.join(DATA_DIR, "maxmind")
RESULTS_DIR = os.path.join(DATA_DIR, "results")

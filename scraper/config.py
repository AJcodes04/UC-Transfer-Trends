"""
Configuration for the assist.org scraper.

WHY this file exists:
  assist.org uses internal numeric IDs to identify institutions. We map human-readable
  UC campus codes (like "UCB") to these IDs so the CLI can accept friendly names while
  the scraper uses the IDs that assist.org's API expects.

  Delay/retry settings are tuned to be polite to assist.org's servers — we're scraping
  a public educational resource, so we want to minimize load.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

# Root of the entire project (parent of scraper/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Where scraped articulation JSON files are saved
OUTPUT_DIR = PROJECT_ROOT / "data" / "articulation"

# Temporary directory for discovery dumps (XHR logs, DOM snapshots)
DISCOVERY_DIR = OUTPUT_DIR / "_discovery"

# Debug directory for screenshots and raw HTML on failures
DEBUG_DIR = OUTPUT_DIR / "_debug"

# ---------------------------------------------------------------------------
# Institution IDs — sourced from assist.org's public /api/institutions endpoint
# ---------------------------------------------------------------------------

# Community colleges: code → assist.org numeric ID
# Full list sourced from assist.org /api/institutions (116 CCs)
CC_INSTITUTIONS: dict[str, dict] = {
    "AHC":      {"id": 110, "name": "Allan Hancock College"},
    "ALAMEDA":  {"id": 111, "name": "College of Alameda"},
    "ARC":      {"id": 27,  "name": "American River College"},
    "AVC":      {"id": 121, "name": "Antelope Valley College"},
    "BAKERFLD": {"id": 84,  "name": "Bakersfield College"},
    "BARSTOW":  {"id": 20,  "name": "Barstow Community College"},
    "BUTTE":    {"id": 8,   "name": "Butte College"},
    "CABRILLO": {"id": 41,  "name": "Cabrillo College"},
    "CAMINO":   {"id": 103, "name": "El Camino College"},
    "CANADA":   {"id": 68,  "name": "Canada College"},
    "CANYONS":  {"id": 140, "name": "College of the Canyons"},
    "CERRITOS": {"id": 104, "name": "Cerritos College"},
    "CERRO":    {"id": 9,   "name": "Cerro Coso Community College"},
    "CHABOT":   {"id": 96,  "name": "Chabot College"},
    "CHAFFEY":  {"id": 69,  "name": "Chaffey College"},
    "CITRUS":   {"id": 97,  "name": "Citrus College"},
    "CLOVIS":   {"id": 150, "name": "Clovis Community College"},
    "COASTLIN": {"id": 105, "name": "Coastline Community College"},
    "COLUMBIA": {"id": 10,  "name": "Columbia College"},
    "COMPTON_OLD": {"id": 34,  "name": "Compton Community College"},
    "COMPTON":  {"id": 153, "name": "Compton College"},
    "CONTRA":   {"id": 28,  "name": "Contra Costa College"},
    "COPPER":   {"id": 112, "name": "Copper Mountain College"},
    "CRAFTON":  {"id": 70,  "name": "Crafton Hills College"},
    "CRC":      {"id": 142, "name": "Cosumnes River College"},
    "CUESTA":   {"id": 16,  "name": "Cuesta College"},
    "CUYAMACA": {"id": 99,  "name": "Cuyamaca College"},
    "CYPRESS":  {"id": 71,  "name": "Cypress College"},
    "DAC":      {"id": 113, "name": "De Anza College"},
    "DESERT":   {"id": 30,  "name": "College of the Desert"},
    "DIABLO":   {"id": 114, "name": "Diablo Valley College"},
    "EVERGRN":  {"id": 2,   "name": "Evergreen Valley College"},
    "FEATHER":  {"id": 122, "name": "Feather River College"},
    "FOLSOM":   {"id": 145, "name": "Folsom Lake College"},
    "FOOTHILL": {"id": 51,  "name": "Foothill College"},
    "FRESNO":   {"id": 35,  "name": "Fresno City College"},
    "FULLRTON": {"id": 134, "name": "Fullerton College"},
    "GAVILAN":  {"id": 72,  "name": "Gavilan College"},
    "GLENDALE": {"id": 43,  "name": "Glendale Community College"},
    "GMCC":     {"id": 106, "name": "Grossmont College"},
    "GWC":      {"id": 55,  "name": "Golden West College"},
    "HARTNELL": {"id": 123, "name": "Hartnell College"},
    "IMPERIAL": {"id": 107, "name": "Imperial Valley College"},
    "IRVINE":   {"id": 124, "name": "Irvine Valley College"},
    "KRC":      {"id": 36,  "name": "Kings River College"},
    "LACC":     {"id": 3,   "name": "Los Angeles City College"},
    "LAEC":     {"id": 118, "name": "East Los Angeles College"},
    "LAHC":     {"id": 31,  "name": "Los Angeles Harbor College"},
    "LAMC":     {"id": 47,  "name": "Los Angeles Mission College"},
    "LANEY":    {"id": 77,  "name": "Laney College"},
    "LAPC":     {"id": 86,  "name": "Los Angeles Pierce College"},
    "LASC":     {"id": 130, "name": "Los Angeles Southwest College"},
    "LASSEN":   {"id": 82,  "name": "Lassen Community College"},
    "LATT":     {"id": 25,  "name": "Los Angeles Trade Technical College"},
    "LAVC":     {"id": 44,  "name": "Los Angeles Valley College"},
    "LAWC":     {"id": 91,  "name": "West Los Angeles College"},
    "LBCC":     {"id": 135, "name": "Long Beach City College"},
    "MARIN":    {"id": 4,   "name": "College of Marin"},
    "MATEO":    {"id": 5,   "name": "College of San Mateo"},
    "MCC":      {"id": 200, "name": "Madera Community College"},
    "MEDANOS":  {"id": 61,  "name": "Los Medanos College"},
    "MENDOCIN": {"id": 100, "name": "Mendocino College"},
    "MERCED":   {"id": 17,  "name": "Merced College"},
    "MERRITT":  {"id": 13,  "name": "Merritt College"},
    "MESA":     {"id": 101, "name": "San Diego Mesa College"},
    "MIRACSTA": {"id": 108, "name": "MiraCosta College"},
    "MIRAMAR":  {"id": 45,  "name": "San Diego Miramar College"},
    "MISSION":  {"id": 32,  "name": "Mission College"},
    "MODESTO":  {"id": 52,  "name": "Modesto Junior College"},
    "MONTEREY": {"id": 133, "name": "Monterey Peninsula College"},
    "MOORPARK": {"id": 139, "name": "Moorpark College"},
    "MTSAC":    {"id": 62,  "name": "Mount San Antonio College"},
    "MTSJC":    {"id": 53,  "name": "Mt. San Jacinto College"},
    "MVC":      {"id": 149, "name": "Moreno Valley College"},
    "NAPA":     {"id": 73,  "name": "Napa Valley College"},
    "NORCO":    {"id": 148, "name": "Norco College"},
    "OCC":      {"id": 74,  "name": "Orange Coast College"},
    "OHLONE":   {"id": 48,  "name": "Ohlone College"},
    "OXNARD":   {"id": 87,  "name": "Oxnard College"},
    "PALOMAR":  {"id": 56,  "name": "Palomar College"},
    "PALOVRDE": {"id": 63,  "name": "Palo Verde College"},
    "PASADENA": {"id": 49,  "name": "Pasadena City College"},
    "PORTER":   {"id": 125, "name": "Porterville College"},
    "POSITAS":  {"id": 18,  "name": "Las Positas College"},
    "RCC":      {"id": 78,  "name": "Riverside City College"},
    "REDWOODS": {"id": 83,  "name": "College of the Redwoods"},
    "RIOHONDO": {"id": 64,  "name": "Rio Hondo College"},
    "RSC":      {"id": 14,  "name": "Rancho Santiago College"},
    "SADDLBK":  {"id": 65,  "name": "Saddleback College"},
    "SANTIAGO":  {"id": 66,  "name": "Santiago Canyon College"},
    "SBCC":     {"id": 92,  "name": "Santa Barbara City College"},
    "SBVC":     {"id": 131, "name": "San Bernardino Valley College"},
    "SCC":      {"id": 126, "name": "Sacramento City College"},
    "SDCC":     {"id": 54,  "name": "San Diego City College"},
    "SEQUOIAS": {"id": 6,   "name": "College of the Sequoias"},
    "SFCITY":   {"id": 33,  "name": "City College of San Francisco"},
    "SHASTA":   {"id": 38,  "name": "Shasta College"},
    "SIERRA":   {"id": 93,  "name": "Sierra College"},
    "SISKIYOU": {"id": 102, "name": "College of the Siskiyous"},
    "SJCC":     {"id": 136, "name": "San Jose City College"},
    "SJDELTA":  {"id": 109, "name": "San Joaquin Delta College"},
    "SKYLINE":  {"id": 127, "name": "Skyline College"},
    "SMCC":     {"id": 137, "name": "Santa Monica College"},
    "SOLANO":   {"id": 94,  "name": "Solano Community College"},
    "SRC":      {"id": 57,  "name": "Santa Rosa Junior College"},
    "SWSTRN":   {"id": 138, "name": "Southwestern College"},
    "TAFT":     {"id": 119, "name": "Taft College"},
    "TAHOE":    {"id": 40,  "name": "Lake Tahoe Community College"},
    "VENTURA":  {"id": 95,  "name": "Ventura College"},
    "VISTA":    {"id": 58,  "name": "Vista Community College"},
    "VVCC":     {"id": 19,  "name": "Victor Valley College"},
    "WCC":      {"id": 147, "name": "Woodland Community College"},
    "WHC":      {"id": 67,  "name": "West Hills College Coalinga"},
    "WHCL":     {"id": 146, "name": "West Hills College Lemoore"},
    "WVC":      {"id": 80,  "name": "West Valley College"},
    "YUBA":     {"id": 90,  "name": "Yuba College"},
}

# UC campuses: code → assist.org numeric ID
UC_INSTITUTIONS: dict[str, dict] = {
    "UCB":  {"id": 79,  "name": "University of California, Berkeley"},
    "UCLA": {"id": 117, "name": "University of California, Los Angeles"},
    "UCSD": {"id": 7,   "name": "University of California, San Diego"},
    "UCD":  {"id": 89,  "name": "University of California, Davis"},
    "UCSB": {"id": 128, "name": "University of California, Santa Barbara"},
    "UCI":  {"id": 120, "name": "University of California, Irvine"},
    "UCSC": {"id": 132, "name": "University of California, Santa Cruz"},
    "UCR":  {"id": 46,  "name": "University of California, Riverside"},
    "UCM":  {"id": 144, "name": "University of California, Merced"},
}

# ---------------------------------------------------------------------------
# Scraping behavior
# ---------------------------------------------------------------------------

# Delay between navigating to each agreement page (seconds).
# Keeps us well under any rate-limit threshold.
PAGE_DELAY = 2.0

# Delay between API calls (seconds). assist.org returns 429 if we go too fast.
# 0.5s per request is safe when combined with the semaphore limiting concurrency.
API_DELAY = 0.5

# Retry settings for failed requests/navigations.
# Uses exponential backoff: 2s → 4s → 8s
MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 4  # seconds — longer backoff for 429s

# Playwright timeouts
NAVIGATION_TIMEOUT = 30_000   # ms — max wait for page navigation
SELECTOR_TIMEOUT = 15_000     # ms — max wait for a DOM element to appear

# ---------------------------------------------------------------------------
# assist.org URLs
# ---------------------------------------------------------------------------

ASSIST_BASE_URL = "https://assist.org"
ASSIST_API_BASE = "https://assist.org/api"

# The results page URL template. Parameters:
#   year         — academic year ID (numeric, from /api/academicyears)
#   institution  — receiving institution ID (the UC)
#   agreement    — sending institution ID (the CC)
RESULTS_URL_TEMPLATE = (
    "{base}/transfer/results?year={year_id}"
    "&institution={receiving_id}&agreement={sending_id}"
    "&agreementType=from&view=agreement&viewBy=major"
)

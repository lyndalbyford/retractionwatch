import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin

st.set_page_config(page_title="Scimex Retraction Checker", layout="wide")

# --- Functions ---
@st.cache_data(ttl=86400)
def load_retracted_dois():
    """Load the Retraction Watch DOI list"""
    url = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
    df = pd.read_csv(url)
    return set(df['RetractionDOI'].dropna().str.strip().str.lower())

def get_story_links(max_pages=3):
    """Crawl Scimex newsfeed for story links"""
    links = set()
    base = "https://www.scimex.org"
    for page in range(max_pages):
        url = f"{base}/newsfeed?page={page}"
        try:
            resp = requests.get(url, timeout=30)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.select('a.story-title'):
                href = a.get('href')
                if href and href.startswith("/newsfeed"):
                    links.add(urljoin(base, href))
        except Exception as e:
            st.warning(f"Error fetching page {page}: {e}")
        time.sleep(1)
    return sorted(list(links))

def extract_dois_from_story(url):
    """Scrape a story page and extract DOIs"""
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        return re.findall(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', text, re.IGNORECASE)
    except Exception as e:
        st.error(f"Error scraping {url}: {e}")
        return []

# --- Streamlit UI ---
st.title("🔬 Scimex Retraction Checker")
st.markdown("This app checks Scimex stories for DOIs that appear on the [Retraction Watch](https://retractionwatch.com) list.")

pages = st.slider("How many pages of Scimex stories to check?", 1, 20, 5)

if st.button("🔍 Run check"):
    with st.spinner("Loading Retraction Watch DOIs..."):
        retracted_dois = load_retracted_dois()
        st.success(f"Loaded {len(retracted_dois):,} retracted DOIs.")

    with st.spinner("Fetching Scimex story links..."):
        story_links = get_story_links(pages)
        st.info(f"Found {len(story_links)} stories to scan.")

    matches = []
    progress = st.progress(0)
    for i, link in enumerate(story_links):
        found_dois = extract_dois_from_story(link)
        for doi in found_dois:
            doi_clean = doi.strip().lower()
            if doi_clean in retracted_dois:
                matches.append({"DOI": doi_clean, "Story URL": link})
        progress.progress((i + 1) / len(story_links))
        time.sleep(0.5)

    if matches:
        st.success(f"⚠️ Found {len(matches)} stories with retracted DOIs.")
        result_df = pd.DataFrame(matches)
        st.dataframe(result_df, use_container_width=True)

        csv = result_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download results as CSV", csv, "retracted_on_scimex.csv", "text/csv")
    else:
        st.success("✅ No retracted DOIs found on Scimex stories.")

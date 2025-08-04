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
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    for page in range(max_pages):
        url = f"{base}/newsfeed?page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=60)
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
    """Extract DOIs and story title from a Scimex article page"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Get the story title
        title_tag = soup.find("h1", class_="title")
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

        # Look inside all div.item elements for DOIs
        dois = []
        for div in soup.find_all("div", class_="item"):
            text = div.get_text()
            found = re.findall(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', text, re.IGNORECASE)
            dois.extend([doi.lower() for doi in found])

        return title, list(set(dois))  # remove duplicates
    except Exception as e:
        st.warning(f"Error scraping {url}: {e}")
        return "Error", []

# --- Streamlit App UI ---
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
        title, found_dois = extract_dois_from_story(link)
        for doi in found_dois:
            if doi in retracted_dois:
                matches.append({
                    "Title": title,
                    "DOI": doi,
                    "URL": link
                })
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

import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET

# Prepare XML namespaces for RSS
ET.register_namespace('atom', "http://www.w3.org/2005/Atom")
ET.register_namespace('media', "http://search.yahoo.com/mrss/")
ET.register_namespace('dc', "http://purl.org/dc/elements/1.1/")

# Fetch the NYT Technology section page
section_url = "https://www.nytimes.com/section/technology"
resp = requests.get(section_url, headers={"User-Agent": "Mozilla/5.0"})
resp.raise_for_status()
soup = BeautifulSoup(resp.text, 'html.parser')

# Start with an empty set
article_links = set()

# 1️⃣ First: Find all article links inside the main stream panel
for a in soup.select('ol[data-testid="stream-panel"] a[data-testid="link"]'):
    href = a.get('href')
    if href and href.startswith('/'):
        full_url = "https://www.nytimes.com" + href
        article_links.add(full_url)

print(f"✅ Found {len(article_links)} article links after stream-panel scrape.")
for link in article_links:
    print(link)

# 2️⃣ Optional: ALSO add links that match NYT's dated URL pattern (but do NOT clear the set)
for a in soup.find_all('a', href=True):
    href = a['href']
    if re.match(r'^/\d{4}/\d{2}/\d{2}/', href):  # URL starts with /YYYY/MM/DD/
        full_url = "https://www.nytimes.com" + href
        article_links.add(full_url)

# 3️⃣ Optional: If STILL empty, fallback to <article> tags (only if article_links is still empty)
if not article_links:
    for article in soup.find_all('article'):
        a = article.find('a', href=True)
        if a:
            url = a['href']
            if url.startswith('/'):
                url = "https://www.nytimes.com" + url
            if re.search(r'/\d{4}/\d{2}/\d{2}/', url):
                article_links.add(url)

print(f"✅ Total unique article links collected: {len(article_links)}")
for link in article_links:
    print(link)

# Set up the RSS root and channel
rss = ET.Element('rss', {
    'version': '2.0',
    'xmlns:atom': "http://www.w3.org/2005/Atom",
    'xmlns:media': "http://search.yahoo.com/mrss/",
    'xmlns:dc': "http://purl.org/dc/elements/1.1/"
})
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = "NYT > Technology"
ET.SubElement(channel, 'link').text = "https://www.nytimes.com/section/technology"
ET.SubElement(channel, 'description').text = (
    "Technology industry news, commentary, and analysis, with reporting on big tech, startups, and internet culture. "
    "The New York Times is a hub for conversation about news and ideas."
)
# Self-referential link to the RSS (optional, identifies the feed URL)
ET.SubElement(channel, 'atom:link', {
    'rel': "self",
    'href': "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    'type': "application/rss+xml"
})

# Helper to convert ISO date to RSS pubDate format
def iso_to_rss_date(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')
    except Exception:
        return None

# Iterate through each article and extract metadata
for url in article_links:
    try:
        art_resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        art_resp.raise_for_status()
    except Exception:
        continue  # skip if any request fails
    art_soup = BeautifulSoup(art_resp.text, 'html.parser')
    item = ET.SubElement(channel, 'item')
    
    # Parse JSON-LD metadata if available
    title = description = pub_date = None
    authors = []
    image_url = image_caption = image_credit = None
    categories = []
    ld_script = art_soup.find('script', type='application/ld+json')
    if ld_script:
        try:
            ld_data = json.loads(ld_script.string)
        except json.JSONDecodeError:
            # Fix any JavaScript quirks if necessary
            ld_data = json.loads(ld_script.string.strip().strip(';'))
        # If multiple JSON-LD entries, find the NewsArticle object
        if isinstance(ld_data, list):
            for entry in ld_data:
                if isinstance(entry, dict) and entry.get('@type') in ('NewsArticle', 'Article'):
                    ld_data = entry
                    break
        # Extract fields from JSON-LD
        title = ld_data.get('headline')
        description = ld_data.get('description')
        # Authors can be list or single
        author_info = ld_data.get('author')
        if author_info:
            if isinstance(author_info, list):
                for auth in author_info:
                    name = auth.get('name')
                    if name: authors.append(name)
            elif isinstance(author_info, dict):
                name = author_info.get('name')
                if name: authors.append(name)
        pub_date = iso_to_rss_date(ld_data.get('datePublished', ''))
        # Image metadata (if present)
        image_info = ld_data.get('image')
        if image_info:
            # If multiple images, use the first one
            if isinstance(image_info, list) and image_info:
                image_info = image_info[0]
            if isinstance(image_info, dict):
                image_url = image_info.get('url') or image_info.get('contentUrl')
                image_caption = image_info.get('caption')
                image_credit = image_info.get('creditText')
            elif isinstance(image_info, str):
                image_url = image_info

    # Fallback to HTML if JSON-LD is missing some info
    if not title:
        # Use the headline from HTML <title> or <h1>
        h1 = art_soup.find('h1')
        if h1: 
            title = h1.get_text(strip=True)
    if not description:
        meta_desc = art_soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '')
    if not pub_date:
        # Try OpenGraph or other meta for date
        meta_time = art_soup.find('meta', attrs={'property': 'article:published_time'})
        if meta_time:
            pub_date = iso_to_rss_date(meta_time.get('content', ''))
    if not authors:
        # Try to find author from byline element (could be <span class="byline">)
        byline = art_soup.find(attrs={'itemprop': 'author'}) or art_soup.find('span', class_='byline')
        if byline:
            # Remove "By " prefix and any extra whitespace
            author_text = byline.get_text(separator=" ").replace('By ', '').strip()
            if author_text:
                # Split by comma or and if multiple authors listed in one string
                if ';' in author_text or ',' in author_text:
                    # split by common separators
                    parts = re.split(';|,| and ', author_text)
                    authors = [part.strip() for part in parts if part.strip()]
                else:
                    authors = [author_text]
    # Categories/keywords
    meta_keys = art_soup.find('meta', attrs={'name': 'keywords'}) or art_soup.find('meta', attrs={'name': 'news_keywords'})
    if meta_keys:
        raw_keys = meta_keys.get('content', '')
        # NYT uses semicolon-separated keywords (as in adx_keywords)
        for key in re.split(';|,', raw_keys):
            key = key.strip()
            if key: 
                categories.append(key)

    # Fill item sub-elements
    ET.SubElement(item, 'title').text = title or "Untitled"
    # Include tracking parameters in link as NYT does
    link_href = url if url.endswith('?partner=rss&emc=rss') else url + '?partner=rss&emc=rss'
    ET.SubElement(item, 'link').text = link_href
    ET.SubElement(item, 'guid', {'isPermaLink': 'true'}).text = link_href
    ET.SubElement(item, 'atom:link', {'rel': 'standout', 'href': link_href})
    ET.SubElement(item, 'description').text = description or ""
    if authors:
        # Join multiple authors with ' and ' (two authors) or commas and 'and' (for three or more)
        author_text = (', '.join(authors[:-1]) + ' and ' + authors[-1]) if len(authors) > 1 else authors[0]
        ET.SubElement(item, 'dc:creator').text = author_text
    if pub_date:
        ET.SubElement(item, 'pubDate').text = pub_date

    # Map keywords to NYT category domains if available
    for cat in categories:
        # Determine domain by simple heuristic based on content
        if re.match(r'^[A-Z][^,]+,\s*[A-Z]', cat):  # format "Lastname, Firstname"
            domain = "http://www.nytimes.com/namespaces/keywords/nyt_per"
        elif re.search(r'\bInc\b|\bCorporation\b|\bCompany\b|\bUniversity\b', cat):
            domain = "http://www.nytimes.com/namespaces/keywords/nyt_org"
        elif re.search(r'\bCity\b|\bStates?\b|\bEurope\b|\bAsia\b|\bAfrica\b|\bAmerica\b', cat):
            domain = "http://www.nytimes.com/namespaces/keywords/nyt_geo"
        else:
            domain = "http://www.nytimes.com/namespaces/keywords/nyt_des"
        ET.SubElement(item, 'category', {'domain': domain}).text = cat

    if image_url:
        media_content = ET.SubElement(item, 'media:content', {
            'url': image_url, 
            'medium': "image"
        })
        if image_credit:
            ET.SubElement(media_content, 'media:credit').text = image_credit
        if image_caption:
            ET.SubElement(media_content, 'media:description').text = image_caption

# ✅ Save to technology.xml inside your Technology repository
with open("technology.xml", "wb") as f:
    ET.ElementTree(rss).write(f, encoding="utf-8", xml_declaration=True)

print("✅ RSS feed saved as 'technology.xml'.")

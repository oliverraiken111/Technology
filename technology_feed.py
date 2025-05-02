import requests
from bs4 import BeautifulSoup
import datetime
import xml.etree.ElementTree as ET

# NYTimes Technology section
url = "https://www.nytimes.com/section/technology"
rss_self_link = "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"

headers = {"User-Agent": "Mozilla/5.0"}

response = requests.get(url, headers=headers)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

# Set up RSS feed with NYT-like namespaces
namespaces = {
    'media': "http://search.yahoo.com/mrss/",
    'dc': "http://purl.org/dc/elements/1.1/",
    'atom': "http://www.w3.org/2005/Atom",
    'nyt': "http://www.nytimes.com/namespaces/rss/2.0"
}
ET.register_namespace('media', namespaces['media'])
ET.register_namespace('dc', namespaces['dc'])
ET.register_namespace('atom', namespaces['atom'])
ET.register_namespace('nyt', namespaces['nyt'])

rss = ET.Element('rss', {
    "version": "2.0",
    "xmlns:media": namespaces['media'],
    "xmlns:dc": namespaces['dc'],
    "xmlns:nyt": namespaces['nyt']
})
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = "NYT > Technology"
ET.SubElement(channel, 'link').text = url
ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link', {
    'href': rss_self_link,
    'rel': 'self',
    'type': 'application/rss+xml'
})
ET.SubElement(channel, 'description').text = "Latest technology news from The New York Times"
ET.SubElement(channel, 'language').text = 'en-us'
ET.SubElement(channel, 'copyright').text = f'Copyright {datetime.datetime.now().year} The New York Times Company'
now_str = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
ET.SubElement(channel, 'lastBuildDate').text = now_str
ET.SubElement(channel, 'pubDate').text = now_str

# Add NYT-style <image>
image = ET.SubElement(channel, 'image')
ET.SubElement(image, 'title').text = "NYT > Technology"
ET.SubElement(image, 'url').text = "https://static01.nyt.com/images/misc/NYT_logo_rss_250x40.png"
ET.SubElement(image, 'link').text = url

# Extract articles
articles_found = 0
seen_titles = set()

for teaser in soup.select('a[data-testid="link"]'):
    h2 = teaser.find('h2')
    if not h2:
        continue  # Skip if no <h2> inside

    title = h2.get_text(strip=True)
    href = teaser.get("href")

    if not title or not href or title in seen_titles:
        continue

    seen_titles.add(title)
    full_url = href if href.startswith("http") else "https://www.nytimes.com" + href

    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = full_url
    ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = full_url
    ET.SubElement(item, '{http://www.w3.org/2005/Atom}link', {
        'href': full_url,
        'rel': 'standout'
    })
    ET.SubElement(item, "description").text = f"NYTimes technology article: {title}"
    ET.SubElement(item, '{http://purl.org/dc/elements/1.1/}creator').text = ""
    ET.SubElement(item, "pubDate").text = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    articles_found += 1
    if articles_found >= 10:
        break

# Write output
with open("technology.xml", "wb") as f:
    ET.ElementTree(rss).write(f, encoding="utf-8", xml_declaration=True)

print(f"✅ RSS feed created with {articles_found} Technology articles.")

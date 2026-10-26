import json
import os
import re
from datetime import datetime
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}

# Matches entries like "July 26th, 2026 - ..." / "September 4th, 2024 — ..."
DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\s*[-—]\s*(.*)",
    re.DOTALL,
)


class EntryParser(HTMLParser):
    """Collects the <i>...</i> blocks that start each update entry, keeping link hrefs."""

    def __init__(self):
        super().__init__()
        self.entries = []       # list of dicts: {date_tuple, lead_text, links}
        self._in_i = 0
        self._buf = []
        self._links = []
        self._blockquote_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "i":
            self._in_i += 1
            self._buf = []
            self._links = []
        elif tag == "a" and self._in_i:
            href = dict(attrs).get("href", "")
            if href and not href.startswith("#"):
                self._links.append(href)
        elif tag == "blockquote":
            self._blockquote_depth += 1

    def handle_endtag(self, tag):
        if tag == "i" and self._in_i:
            self._in_i -= 1
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            m = DATE_RE.match(text)
            if m:
                month = MONTHS[m.group(1)]
                self.entries.append({
                    "month": month,
                    "day": int(m.group(2)),
                    "year": int(m.group(3)),
                    "lead": m.group(4).strip(),
                    "links": self._links,
                })
        elif tag == "blockquote":
            self._blockquote_depth = max(0, self._blockquote_depth - 1)

    def handle_data(self, data):
        if self._in_i and not self._blockquote_depth:
            self._buf.append(data)

    def handle_entityref(self, name):
        if self._in_i and not self._blockquote_depth:
            self._buf.append(f"&{name};")


def parse_updates(html):
    parser = EntryParser()
    parser.feed(html)
    # The page lists newest first; keep document order for the feed.
    entries = []
    for e in parser.entries:
        iso = f"{e['year']:04d}-{e['month']:02d}-{e['day']:02d}"
        entries.append({
            "id": iso,
            "date": iso,
            "title": e["lead"],
            "links": e["links"],
        })
    return entries


def build_description(entry):
    """Lead text plus the announcement link, like the original's description builder."""
    desc = f"{entry['date']} — {entry['title']}"
    if entry["links"]:
        desc += f"\nLink: {entry['links'][0]}"
    return desc


def generate_rss(entries, output_file="updates.rss"):
    """
    Generate RSS feed from SSI update entries.
    """
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    # Channel metadata
    ET.SubElement(channel, "title").text = "SSI Updates"
    ET.SubElement(channel, "description").text = "Latest updates from Safe Superintelligence Inc."
    ET.SubElement(channel, "link").text = "https://ssi.inc/updates"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

    for entry in entries:
        item = ET.SubElement(channel, "item")

        title = f"{entry['date']} - {entry['title']}"
        ET.SubElement(item, "title").text = title

        link = entry["links"][0] if entry["links"] else "https://ssi.inc/updates"
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid").text = str(entry.get("id", ""))

        ET.SubElement(item, "description").text = build_description(entry)

        first_seen = entry.get("first_seen")
        if first_seen:
            try:
                dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
                pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
            except (ValueError, AttributeError):
                pub_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        else:
            pub_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item, "pubDate").text = pub_date

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ", level=0)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"RSS feed generated: {output_file}")


def process_entries(data, db_file):
    """
    Processes entries from the scraped page, compares them with an existing database,
    generates the RSS feed, and updates the database.
    """
    # --- 1. Load existing entries from our database file ---
    existing_entries = []
    if os.path.exists(db_file):
        try:
            with open(db_file, "r", encoding="utf-8") as f:
                existing_entries = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from '{db_file}'. Starting fresh.")
            existing_entries = []

    # --- 2. Map existing entry IDs for first_seen lookups ---
    existing_entries_map = {entry.get("id"): entry for entry in existing_entries if entry.get("id")}

    # --- 3. Find new entries and build the current list ---
    new_additions = []
    all_current = []
    current_time = datetime.now().isoformat() + "Z"

    for entry in data:
        entry_id = entry.get("id")
        if entry_id and entry_id in existing_entries_map:
            # Existing entry - preserve the first_seen timestamp
            existing_entry = existing_entries_map[entry_id]
            entry["first_seen"] = existing_entry.get("first_seen", current_time)
        else:
            # New entry - set first_seen to current time
            entry["first_seen"] = current_time
            if entry_id:
                new_additions.append(entry)
        all_current.append(entry)

    # --- 4. Generate the RSS feed ---
    generate_rss(all_current)

    # --- 5. Report new additions ---
    if new_additions:
        print(f"Found {len(new_additions)} new update entries.")
        for entry in new_additions:
            print(f"- {entry['date']} - {entry['title'][:80]}")
    else:
        print("No new update entries found.")

    # --- 6. Save the complete list back to the DB file ---
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(all_current, f, ensure_ascii=False, indent=4)

    print(f"\nUpdated database saved to '{db_file}' with {len(all_current)} total update entries.")


def main():
    source_html_file = "updates.html"
    database_json_file = "updates_entries.json"

    try:
        with open(source_html_file, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print(f"Error: Source file '{source_html_file}' not found.")
        return

    data = parse_updates(html)
    if not data:
        print("No update entries parsed from the page - the site layout may have changed.")
        return

    process_entries(data, database_json_file)


if __name__ == "__main__":
    main()
import subprocess
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
import re
import math
from concurrent.futures import ThreadPoolExecutor

class mainWeb:

    def __init__(self):
        self.based_url = "https://www.pbc.gov.cn"
        self.main_url = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html"
        self.page_turning_url = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/17105-{page_number}.html"

    def fetch_html_with_curl(self, url=None):
        if url is None:
            url = self.main_url
        curl_command = ["curl", url]
        proc = subprocess.run(
            curl_command, capture_output=True,
            text=False, check=False
        )
        html = proc.stdout.decode("utf-8")
        return html

    def fetch_links_for_rows(self, num_rows: int) -> pd.DataFrame:
        """
        Fetch enough listing pages to cover num_rows records in parallel.
        Page 1  → index.html
        Page N  → 17105-(N-1).html  (for N >= 2, max N = 100)
        Returns a DataFrame trimmed to exactly num_rows rows.
        """
        # Fetch extra pages to ensure enough unique links after deduplication
        pages_needed = min(math.ceil(num_rows / 20) + 2, 100)

        def fetch_page(page):
            url = self.main_url if page == 1 else self.page_turning_url.format(page_number=page - 1)
            print(f"Fetching listing page {page}/{pages_needed}...")
            html = self.fetch_html_with_curl(url)
            return page, self.convert_links_to_dataframe(html)

        with ThreadPoolExecutor(max_workers = pages_needed) as executor:
            page_results = list(executor.map(fetch_page, range(1, pages_needed + 1)))

        # Sort by page number to preserve chronological order
        page_results.sort(key=lambda x: x[0])
        all_records = pd.concat([df for _, df in page_results], ignore_index=True)

        return (all_records
                .drop_duplicates(subset='url')
                .reset_index(drop=True)
                .head(num_rows)
                .reset_index(drop=True))

    def convert_links_to_dataframe(self, html):

        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one("#r_con") or soup

        records = [ ]

        for a in container.select('a[istitle="true"][href]'):
            href = (a.get("href") or "").strip()

            if not re.search(r"/125207/125217/125925/\d+/index\.html$", href):
                continue

            full_url = urljoin(self.based_url, href)
            text_title = a.get_text(strip = True)

            date_str = ""
            td = a.find_parent("td")
            if td:
                span = td.find("span", class_ = "hui12")
                if span:
                    date_str = span.get_text(strip = True)

            records.append({
                "title": text_title,
                "url": full_url,
                "date": date_str
            })
        links = pd.DataFrame(records, columns = ["title", "url", "date"])
        return links

if __name__ == "__main__":
    web = mainWeb()
    html = web.fetch_html_with_curl()
    print(html)

    links_df = web.convert_links_to_dataframe(html)
    print(links_df)

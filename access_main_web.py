import subprocess
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
import re

class mainWeb:

    def __init__(self):
        self.based_url = "https://www.pbc.gov.cn"
        self.main_url = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html"
        self.page_turning_url = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/17105-1.html"

    def fetch_html_with_curl(self):

        curl_command = [
            "curl",
            self.main_url
        ]
        proc = subprocess.run(
            curl_command, capture_output = True,
            text = False, check = False
        )
        html = proc.stdout.decode("utf-8")
        return html

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

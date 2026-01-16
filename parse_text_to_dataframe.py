from bs4 import BeautifulSoup
import pandas as pd
import re
import subprocess
import html as ihtml
from datetime import datetime

class TextToDataFrameParser:

    def __init__(self):

        self.base_url = "https://www.pbc.gov.cn"
        self.main_url = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html"
        self.page_turning_url = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/17105-1.html"

        self.CN_TO_ISO = {
            "人民币": "CNY", "美元": "USD", "欧元": "EUR", "日元": "JPY", "港元": "HKD", "英镑": "GBP",
            "澳大利亚元": "AUD", "新西兰元": "NZD", "新加坡元": "SGD", "瑞士法郎": "CHF",
            "加拿大元": "CAD", "澳门元": "MOP", "林吉特": "MYR", "俄罗斯卢布": "RUB",
            "南非兰特": "ZAR", "韩元": "KRW", "阿联酋迪拉姆": "AED", "沙特里亚尔": "SAR",
            "匈牙利福林": "HUF", "波兰兹罗提": "PLN", "丹麦克朗": "DKK", "瑞典克朗": "SEK",
            "挪威克朗": "NOK", "土耳其里拉": "TRY", "墨西哥比索": "MXN", "泰铢": "THB",
        }

        self.pattern = re.compile(r'(?P<left_amt>\d+)(?P<left_ccy>[\u4e00-\u9fa5]+)对人民币(?P<rate>[\d\.]+)元')
        self.pattern_cny_base = re.compile(r'人民币(?P<left_amt>\d+)元对(?P<rate>[\d\.]+)(?P<right_ccy>[\u4e00-\u9fa5]+)')

    def fetch_html_with_curl(self, url):

        curl_command = [
            "curl",
            url
        ]
        proc = subprocess.run(
            curl_command, capture_output = True,
            text = False, check = False
        )
        html = proc.stdout.decode("utf-8")
        return html
    
    @staticmethod
    def extract_text(html):
        
        # Unscape HTML to get clean text
        unescaped = ihtml.unescape(html)

        soup = BeautifulSoup(unescaped, "html.parser")

        zoom_div = soup.find("div", id = "zoom")

        if not zoom_div:
            candidate_text = soup.get_text(separator = " ", strip = True)
        else: 
            candidate_text = zoom_div.get_text(separator = " ", strip = True)
        
        candidate_text = re.sub(r'\s+', ' ', candidate_text).strip()

        pattern = (
            r'中国人民银行授权中国外汇交易中心公布，'
            r'\d{4}年\d{1,2}月\d{1,2}日银行间外汇市场人民币汇率中间价为'
            r'.*?泰铢。'
        )
        
        m = re.search(pattern, candidate_text)

        if not m: 
            raise ValueError("Could not find the expected text pattern in the HTML content.")
        text = m.group(0)
        return text

    @staticmethod
    def separate_Chinese_text(text):
        # Split by '，' and remove trailing '。'
        parts = [p.rstrip('。') for p in text.split('，')]
        second_part = parts[1].split('为')

        parts[1:2] = second_part
        return parts
    
    def extract_fx(self, fx_list): 

        fx_map = { }

        for item in fx_list:
            m = self.pattern.search(item)
            if m:
                left_amt = int(m.group("left_amt"))
                left_ccy = m.group("left_ccy")
                rate = float(m.group("rate"))

                if left_ccy in self.CN_TO_ISO:
                    iso_ccy = self.CN_TO_ISO[left_ccy]
                    # Construct USD/CNY style, include amount prefix if not 1
                    if left_amt == 1:
                        pair = f"{iso_ccy}/CNY"
                    else:
                        pair = f"{left_amt}{iso_ccy}/CNY"
                    fx_map[pair] = rate
                continue

            m = self.pattern_cny_base.search(item)
            if m:
                amt = m.group("left_amt")
                ccy_ch = m.group("right_ccy")
                rate = float(m.group("rate"))

                if ccy_ch in self.CN_TO_ISO:
                    iso = self.CN_TO_ISO[ccy_ch]
                    # Construct CNY/100JPY style
                    pair = f"CNY/{iso}"
                    fx_map[pair] = rate
                continue
        df = pd.DataFrame([fx_map])
        return df
    
if __name__ == "__main__":
    web = TextToDataFrameParser()
    html = web.fetch_html_with_curl("https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/2026011609055116437/index.html")
    print(html)

    links_df = web.extract_text(html)
    print(links_df)

    parts = web.separate_Chinese_text(links_df)
    print(parts)

    df = web.extract_fx(parts)
    print(df)
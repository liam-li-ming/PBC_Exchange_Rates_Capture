# PBC Exchange Rates Capture

A Python tool that scrapes the **People's Bank of China (PBC)** official website to capture daily CNY central parity exchange rates and exports them to Excel.

---

## Overview

The PBC publishes daily interbank foreign exchange market CNY central parity rates on its website. This project automates:

1. Fetching the PBC's exchange rate listing page
2. Discovering all available daily rate pages and their dates
3. Parsing the Chinese-language rate text from each daily page
4. Mapping Chinese currency names to ISO 4217 currency codes
5. Exporting all results to a dated Excel file

---

## Project Structure

```
PBC_Exchange_Rates_Capture/
├── main.py                      # Entry point — orchestrates the full pipeline
├── access_main_web.py           # Fetches the main listing page and extracts links
├── parse_text_to_dataframe.py   # Fetches individual rate pages and parses FX data
└── PBC_Exchange_Rates_YYYY-MM-DD.xlsx   # Output file (gitignored)
```

---

## Dependencies

| Package          | Purpose                                      |
|------------------|----------------------------------------------|
| `beautifulsoup4` | HTML parsing                                 |
| `lxml`           | HTML parser backend for BeautifulSoup        |
| `pandas`         | DataFrame construction and Excel export      |
| `curl`           | System CLI tool used to fetch web pages      |

> `curl` must be available on the system PATH. It is used instead of Python's `urllib`/`requests` to reliably handle the PBC website's encoding and SSL behaviour.

Install Python dependencies:

```bash
pip install beautifulsoup4 lxml pandas openpyxl
```

---

## How to Run

```bash
python main.py
```

The script prints progress to the console and writes an Excel file to the same directory:

```
PBC_Exchange_Rates_YYYY-MM-DD.xlsx
```

---

## Detailed Workflow

### Step 1 — Fetch the Main Listing Page (`access_main_web.py`)

**Class:** `mainWeb`

The PBC listing page URL is:
```
https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html
```

**`fetch_html_with_curl()`**

- Runs `curl <url>` via `subprocess.run()`
- Captures the raw bytes from stdout and decodes them as UTF-8
- Returns the full HTML string of the listing page

**`convert_links_to_dataframe(html)`**

- Parses the HTML with BeautifulSoup (lxml parser)
- Targets the `#r_con` container element (the main content area)
- Selects all `<a>` tags with the attribute `istitle="true"` that have an `href`
- Filters links whose `href` matches the pattern:
  ```
  /125207/125217/125925/{id}/index.html
  ```
  This ensures only daily rate detail pages are collected, not navigation or unrelated links.
- For each matching link:
  - Constructs the full URL by joining with the base domain `https://www.pbc.gov.cn`
  - Extracts the link's text as the title
  - Looks for the date in a sibling `<span class="hui12">` element within the same `<td>`
- Returns a `pandas.DataFrame` with columns: `title`, `url`, `date`

---

### Step 2 — Parallel Processing of Daily Rate Pages (`main.py`)

**Function:** `process_single_date(d, url)`

`main.py` iterates over every row in the links DataFrame (each row is one trading day) and spawns up to **20 concurrent threads** using `ThreadPoolExecutor` to process all dates in parallel.

For each date and URL, the inner function:

1. Calls `TextToDataFrameParser.fetch_html_with_curl(url)` to download the daily detail page
2. Calls `extract_text(html)` to isolate the rate announcement text
3. Calls `separate_Chinese_text(text)` to split the announcement into individual rate clauses
4. Calls `extract_fx(parts)` to parse each clause into a currency pair and rate
5. Inserts the `date` column as the first column
6. Returns a single-row `DataFrame` for that trading day

Failed dates are caught by a `try/except` block, logged, and skipped (returning `None`). All successful results are concatenated into one combined DataFrame.

---

### Step 3 — Fetch Individual Rate Page HTML (`parse_text_to_dataframe.py`)

**Class:** `TextToDataFrameParser`

**`fetch_html_with_curl(url)`**

- Identical mechanism to `mainWeb.fetch_html_with_curl()`: runs `curl <url>` as a subprocess
- Decodes the response bytes as UTF-8
- Returns the raw HTML of one daily rate detail page

---

### Step 4 — Extract the Rate Announcement Text

**`extract_text(html)` (static method)**

The daily page contains a `<div id="zoom">` element with the article body. The method:

1. **HTML-unescapes** the raw HTML to resolve entities like `&nbsp;` and `&amp;`
2. Parses with BeautifulSoup (`html.parser`)
3. Targets `<div id="zoom">` for text extraction; falls back to the full document body if not found
4. Collapses all whitespace to single spaces
5. Applies a **regex anchor pattern** to extract exactly the rate announcement sentence:
   ```
   中国人民银行授权中国外汇交易中心公布，
   {YYYY}年{M}月{D}日银行间外汇市场人民币汇率中间价为
   ...泰铢。
   ```
   The pattern anchors to the standard PBC preamble and ends at `泰铢。` (Thai Baht — always the last listed currency).
6. Raises `ValueError` if the pattern is not found (e.g., on holidays or non-trading days)
7. Returns the matched sentence string

---

### Step 5 — Split the Announcement into Clauses

**`separate_Chinese_text(text)` (static method)**

The PBC announcement is a single long sentence, comma-delimited. This method:

1. Splits the text on `，` (Chinese comma)
2. Strips trailing `。` (Chinese full stop) from each part
3. Further splits the second segment on `为` to separate the date header from the first rate clause
4. Returns a flat list of string parts, each containing one rate statement

Example parts after splitting:
```
["中国人民银行授权中国外汇交易中心公布", "2026年3月7日银行间外汇市场人民币汇率中间价", "1美元对人民币7.1732元", "1欧元对人民币7.8001元", ...]
```

---

### Step 6 — Parse FX Rates into a DataFrame

**`extract_fx(fx_list)`**

Iterates over each clause and applies one of two regex patterns:

**Pattern A — Foreign currency quoted against CNY:**
```
(?P<left_amt>\d+)(?P<left_ccy>[\u4e00-\u9fa5]+)对人民币(?P<rate>[\d\.]+)元
```
Example match: `1美元对人民币7.1732元`
- `left_amt` = `1`, `left_ccy` = `美元`, `rate` = `7.1732`
- Produces pair: `USD/CNY = 7.1732`
- For units other than 1 (e.g., 100 JPY): produces `100JPY/CNY`

**Pattern B — CNY quoted against foreign currency:**
```
人民币(?P<left_amt>\d+)元对(?P<rate>[\d\.]+)(?P<right_ccy>[\u4e00-\u9fa5]+)
```
Example match: `人民币100元对114.63港元`
- Produces pair: `CNY/HKD = 114.63`

The method uses a **Chinese-to-ISO currency mapping dictionary** (`CN_TO_ISO`) covering 26 currencies:

| Chinese | ISO | Chinese | ISO |
|---------|-----|---------|-----|
| 美元 | USD | 欧元 | EUR |
| 日元 | JPY | 港元 | HKD |
| 英镑 | GBP | 澳大利亚元 | AUD |
| 新西兰元 | NZD | 新加坡元 | SGD |
| 瑞士法郎 | CHF | 加拿大元 | CAD |
| 澳门元 | MOP | 林吉特 | MYR |
| 俄罗斯卢布 | RUB | 南非兰特 | ZAR |
| 韩元 | KRW | 阿联酋迪拉姆 | AED |
| 沙特里亚尔 | SAR | 匈牙利福林 | HUF |
| 波兰兹罗提 | PLN | 丹麦克朗 | DKK |
| 瑞典克朗 | SEK | 挪威克朗 | NOK |
| 土耳其里拉 | TRY | 墨西哥比索 | MXN |
| 泰铢 | THB | 人民币 | CNY |

Returns a single-row `pandas.DataFrame` where each column is a currency pair (e.g., `USD/CNY`, `EUR/CNY`, `CNY/HKD`) and the value is the mid-point exchange rate.

---

### Step 7 — Combine and Export (`main.py`)

After all threads complete:

1. `None` results (failed dates) are filtered out
2. All single-row DataFrames are concatenated with `pd.concat(..., ignore_index=True)`
3. The final DataFrame has one row per trading day and one column per currency pair, with a leading `date` column
4. Exported to Excel using `df.to_excel()`:
   ```
   PBC_Exchange_Rates_YYYY-MM-DD.xlsx
   ```
   where the date is today's run date, not the rate date.

---

## Output Format

The Excel file contains one row per trading day with the following structure:

| date | USD/CNY | EUR/CNY | 100JPY/CNY | HKD/CNY | GBP/CNY | ... | CNY/HKD |
|------|---------|---------|------------|---------|---------|-----|---------|
| 2026-03-07 | 7.1732 | 7.8001 | 4.6821 | 0.9245 | 9.0315 | ... | 114.63 |
| 2026-03-06 | 7.1753 | 7.7998 | ... | | | | |

- Dates come from the PBC listing page text (as published by the PBC)
- Currency pairs with amounts other than 1 unit (e.g., 100 JPY) are prefixed with the unit count

---

## Data Source

All data is sourced from the official People's Bank of China website:

- **Listing page:** `https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html`
- **Rate detail pages:** `https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/{id}/index.html`

The rates represent the **interbank foreign exchange market CNY central parity rates** as authorised by the PBC and published by the China Foreign Exchange Trade System (CFETS).

---

## Notes

- The script only processes dates available on the current listing page. It does not paginate to historical archives.
- If the user needs more historical data, the listing page should set to as the following, where the **index** variable can be set from 1 to **当前页: 1/143** maximum, as of the testing date 2026-03-07. 
- `https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/17105-{index}.html`

- On non-trading days (weekends, public holidays), the PBC does not publish rates; those URLs will raise a `ValueError` inside `extract_text()` and be skipped.

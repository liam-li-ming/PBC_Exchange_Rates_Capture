import access_main_web
import parse_text_to_dataframe
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import os

def run(num_rows: int = 20):
    web = access_main_web.mainWeb()
    par = parse_text_to_dataframe.TextToDataFrameParser()

    print(f"Fetching listing pages for {num_rows} rows of data...")
    links = web.fetch_links_for_rows(num_rows)

    # Process each date's FX data in parallel
    def process_single_date(d, url):
        try:
            print(f"Processing FX on {d}")
            html = par.fetch_html_with_curl(url)
            text = par.extract_text(html)
            parts = par.separate_Chinese_text(text)
            df_fx = par.extract_fx(parts)
            # Make the date column first
            df_fx.insert(0, 'date', d)
            return df_fx
        
        except Exception as e:
            print(f"Error processing {d} ({url}): {e}")
            return None

    with ThreadPoolExecutor(max_workers = len(links)) as executor:
        results = list(executor.map(lambda x: process_single_date(x[0], x[1]),
                                    zip(links['date'], links['url'])))

    # Filter out None results from errors
    results = [r for r in results if r is not None]

    if not results:
        raise ValueError("No data was successfully processed")

    df_all = pd.concat(results, ignore_index = True)
    
    print("Preparing the FX report:")
    print("Exporting to Excel...")

    today = datetime.now().strftime('%Y-%m-%d')

    # Save to Excel in the same directory as the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, f"PBC_Exchange_Rates_{today}.xlsx")
    df_all.to_excel(output_path, index = False)

    print(df_all.to_string())

if __name__ == "__main__":
    while True:
        try:
            num_rows = int(input("How many historical records would you like to retrieve? (1–2000): "))
            if 1 <= num_rows <= 2000:
                break
            print("Please enter a number between 1 and 2000.")
        except ValueError:
            print("Invalid input. Please enter a whole number.")
    run(num_rows)
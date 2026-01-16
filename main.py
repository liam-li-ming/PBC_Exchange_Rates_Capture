import access_main_web
import parse_text_to_dataframe
import pandas as pd
from datetime import datetime

def run():
    main_url = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html"
    web = access_main_web.mainWeb()
    par = parse_text_to_dataframe.TextToDataFrameParser()
    
    print("Fetching main page HTML...")

    html = web.fetch_html_with_curl()
    print("Extracting links to DataFrame...")
    links = web.convert_links_to_dataframe(html)

    # Create an empty DataFrame to hold all results
    df_all = pd.DataFrame()

    for d, item in zip(links['date'], links['url']):
        print(f"Processing FX on {d}")

        df_date = pd.DataFrame({'date': [d]})
        html = par.fetch_html_with_curl(item)
        text = par.extract_text(html)
        parts = par.separate_Chinese_text(text)
        df_fx = par.extract_fx(parts)

        df_day = pd.concat([df_date, df_fx], axis = 1)

        df_all = pd.concat([df_all, df_day], ignore_index = True)
    
    print("Preparing the FX report:")
    print("Exporting to Excel...")

    today = datetime.now().strftime('%Y-%m-%d')
    df_all.to_excel(f"PBC_Exchange_Rates_{today}.xlsx", index = False)

    print(df_all)

if __name__ == "__main__":
    run()
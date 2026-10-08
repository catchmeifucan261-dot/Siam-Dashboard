import pdfplumber
import pandas as pd
import re

def get_main_category(commodity_name):
    """Maps all SIAM sub-commodities to their main category."""
    mapping = {
        'HR Steel': 'Iron & Steel', 'CR Steel': 'Iron & Steel', 'Alloy Steel': 'Iron & Steel',
        'Pig Iron': 'Iron & Steel', 'Stainless Steel': 'Iron & Steel', 'Steel Scrap': 'Iron & Steel',
        'Coal': 'Iron & Steel', 'Iron Ore': 'Iron & Steel',
        'Aluminium': 'Non-Ferrous Metals', 'Copper': 'Non-Ferrous Metals', 'Lead': 'Non-Ferrous Metals',
        'Nickel': 'Non-Ferrous Metals', 'Zinc': 'Non-Ferrous Metals', 'Platinum': 'Non-Ferrous Metals',
        'Palladium': 'Non-Ferrous Metals', 'Rhodium': 'Non-Ferrous Metals',
        'Poly Propylene': 'Polymers', 'ABS': 'Polymers', 'Acrylonitrile Butadiene': 'Polymers', 'Poly Carbonate': 'Polymers',
        'UREA': 'Chemicals',
        'Natural Rubber': 'Rubber', 'Synthetic Rubber': 'Rubber', 'EPDM': 'Rubber',
        'Ethylene Propylene': 'Rubber', 'Carbon Black': 'Rubber', 'Polybutadiene': 'Rubber',
        'Lithium': 'Advanced Chemistries', 'Cobalt': 'Advanced Chemistries',
        'Magnet': 'Rare Earth Elements', 'NdFeB': 'Rare Earth Elements',
        'Crude Oil': 'Crude / Petroleum', 'CNG': 'Crude / Petroleum', 'Petrol': 'Crude / Petroleum', 'Diesel': 'Crude / Petroleum',
        'US Dollar': 'Forex Movement', 'Pound Sterling': 'Forex Movement', 'Euro': 'Forex Movement', 'Yen': 'Forex Movement',
        'Renminbi': 'Forex Movement', 'CNY': 'Forex Movement',
        'Ethanol': 'Other Rates', 'Cash Reserve': 'Other Rates', 'Bank Rate': 'Other Rates', 'Base Rate': 'Other Rates',
        'Baltic Dry Index': 'Other Rates'
    }
    for key, category in mapping.items():
        if key.lower() in commodity_name.lower():
            return category
    return "Other Commodities"

def clean_val(val_str):
    if not val_str or str(val_str).strip() in ['-', '', '*']: 
        return None
    val_str = str(val_str).replace(',', '').strip()
    
    # Handle ranges (e.g., 50,000-52,000) by taking the arithmetic mean
    if '-' in val_str and val_str.count('-') == 1 and not val_str.startswith('-'):
        parts = val_str.split('-')
        try:
            return (float(parts[0]) + float(parts[1])) / 2
        except: 
            pass
        
    try:
        return float(re.sub(r'[^\d.]', '', val_str))
    except:
        return None

def process_siam_pdf(file_path):
    """Extracts standard tables, Forex, Crude, and Other Rate structures."""
    extracted_data = []
    months_short = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
    months_long = ['April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March']
    
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            tables = page.extract_tables()
            
            page_context = "Unknown"
            if "Crude Oil Prices" in text or "Europe Brent Spot Price FOB" in text: page_context = "Crude Oil"
            elif "Compressed Natural Gas" in text or "CNG" in text: page_context = "CNG"
            elif "Petrol-Diesel" in text: page_context = "Petrol-Diesel"
            elif "Rupees per Unit of US Dollar" in text: page_context = "US Dollar"
            elif "Pound Sterling" in text: page_context = "Pound Sterling"
            elif "Unit of Euro" in text or "INR/EURO" in text: page_context = "Euro"
            elif "100 Yen" in text: page_context = "Yen"
            elif "Renminbi" in text: page_context = "Renminbi"
            elif "Ethanol Prices" in text: page_context = "Ethanol"
            elif "Baltic Dry Index" in text: page_context = "Baltic Dry Index"
            
            fy_matches = re.findall(r'20(\d{2})-\d{2}', text)
            fy1 = fy_matches[0] if len(fy_matches) > 0 else "25"
            fy2 = fy_matches[1] if len(fy_matches) > 1 else str(int(fy1) + 1)
            
            current_commodity = "Unknown"
            current_unit = "Unknown"
            
            for table in tables:
                for row in table:
                    if not row or not row[0]: 
                        continue
                    col0 = str(row[0]).strip().replace('\n', ' ')
                    
                    if "Commodity" in col0 and len(row) > 1 and row[1]:
                        current_commodity = str(row[1]).strip().replace('\n', ' ')
                    if "Month-Year" in col0 and len(row) > 1 and row[1]:
                        current_unit = str(row[1]).strip().replace('\n', ' ')
                        
                    is_date_row = re.match(r'^[a-zA-Z]{3,4}\s*\-?\s*\d{2}$', col0)
                    
                    if is_date_row:
                        date_str = col0.replace(' ', '')
                        
                        if current_commodity != "Unknown" and len(row) > 1:
                            val = clean_val(row[1])
                            if val is not None:
                                extracted_data.append({
                                    'Main Category': get_main_category(current_commodity), 
                                    'Commodity': current_commodity, 
                                    'Date': date_str, 
                                    'Price': val, 
                                    'Unit': current_unit
                                })
                        
                        elif page_context == "Crude Oil" and len(row) > 1:
                            val = clean_val(row[1])
                            if val is not None: 
                                extracted_data.append({'Main Category': 'Crude / Petroleum', 'Commodity': 'Crude Oil', 'Date': date_str, 'Price': val, 'Unit': '$/Barrel'})
                                
                        elif page_context == "CNG" and len(row) >= 3:
                            v_del, v_mum = clean_val(row[1]), clean_val(row[2])
                            if v_del is not None: extracted_data.append({'Main Category': 'Crude / Petroleum', 'Commodity': 'CNG - Delhi', 'Date': date_str, 'Price': v_del, 'Unit': '₹/kg'})
                            if v_mum is not None: extracted_data.append({'Main Category': 'Crude / Petroleum', 'Commodity': 'CNG - Mumbai', 'Date': date_str, 'Price': v_mum, 'Unit': '₹/kg'})
                                
                        elif page_context == "Petrol-Diesel" and len(row) >= 5:
                            p_del, d_del, p_mum, d_mum = clean_val(row[1]), clean_val(row[2]), clean_val(row[3]), clean_val(row[4])
                            if p_del is not None: extracted_data.append({'Main Category': 'Crude / Petroleum', 'Commodity': 'Petrol - Delhi', 'Date': date_str, 'Price': p_del, 'Unit': '₹/Litre'})
                            if d_del is not None: extracted_data.append({'Main Category': 'Crude / Petroleum', 'Commodity': 'Diesel - Delhi', 'Date': date_str, 'Price': d_del, 'Unit': '₹/Litre'})
                            if p_mum is not None: extracted_data.append({'Main Category': 'Crude / Petroleum', 'Commodity': 'Petrol - Mumbai', 'Date': date_str, 'Price': p_mum, 'Unit': '₹/Litre'})
                            if d_mum is not None: extracted_data.append({'Main Category': 'Crude / Petroleum', 'Commodity': 'Diesel - Mumbai', 'Date': date_str, 'Price': d_mum, 'Unit': '₹/Litre'})

                        elif page_context == "Ethanol" and len(row) >= 4:
                            v1, v2, v3 = clean_val(row[1]), clean_val(row[2]), clean_val(row[3])
                            if v1 is not None: extracted_data.append({'Main Category': 'Other Rates', 'Commodity': 'Ethanol - Sugarcane Juice', 'Date': date_str, 'Price': v1, 'Unit': '₹/Litre'})
                            if v2 is not None: extracted_data.append({'Main Category': 'Other Rates', 'Commodity': 'Ethanol - B-Heavy Molasses', 'Date': date_str, 'Price': v2, 'Unit': '₹/Litre'})
                            if v3 is not None: extracted_data.append({'Main Category': 'Other Rates', 'Commodity': 'Ethanol - C-Heavy Molasses', 'Date': date_str, 'Price': v3, 'Unit': '₹/Litre'})

                        elif page_context == "Baltic Dry Index" and len(row) > 1:
                            val = clean_val(row[1])
                            if val is not None: extracted_data.append({'Main Category': 'Other Rates', 'Commodity': 'Baltic Dry Index', 'Date': date_str, 'Price': val, 'Unit': 'Points'})

                    elif col0 in months_short or col0 in months_long:
                        short_m = col0[:3]
                        if short_m == 'Jun': short_m = 'June'
                        if short_m == 'Jul': short_m = 'July'
                        if short_m == 'Sep': short_m = 'Sept'
                        
                        month_idx = 0
                        for idx, m in enumerate(['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']):
                            if m in col0: month_idx = idx
                            
                        is_next_year = month_idx >= 9
                        yr1_str = f"{short_m}-{str(int(fy1)+1) if is_next_year else fy1}"
                        yr2_str = f"{short_m}-{str(int(fy2)+1) if is_next_year else fy2}"
                        
                        if page_context in ["US Dollar", "Pound Sterling", "Euro", "Yen", "Renminbi"]:
                            unit_map = {"US Dollar": "₹/USD", "Pound Sterling": "₹/GBP", "Euro": "₹/EUR", "Yen": "₹/100Yen", "Renminbi": "₹/CNY"}
                            unit = unit_map.get(page_context, "₹")
                            
                            if len(row) >= 3:
                                val1 = clean_val(row[1])
                                if val1 is not None: extracted_data.append({'Main Category': 'Forex Movement', 'Commodity': page_context, 'Date': yr1_str, 'Price': val1, 'Unit': unit})
                            if len(row) >= 5:
                                val2 = clean_val(row[3])
                                if val2 is not None: extracted_data.append({'Main Category': 'Forex Movement', 'Commodity': page_context, 'Date': yr2_str, 'Price': val2, 'Unit': unit})

    df = pd.DataFrame(extracted_data)
    
    if not df.empty:
        df['Date'] = df['Date'].str.replace('Sept', 'Sep').str.replace('July', 'Jul').str.replace('June', 'Jun')
        df['Date'] = pd.to_datetime(df['Date'], format='%b-%y', errors='coerce')
        df.dropna(subset=['Date'], inplace=True)
        df.sort_values(by=['Commodity', 'Date'], inplace=True)
        df.drop_duplicates(subset=['Commodity', 'Date'], keep='last', inplace=True)
        
    return df
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
from extractor import process_siam_pdf

# --- UI Configuration & File System Setup ---
st.set_page_config(page_title="SIAM Commodity Monitor", layout="wide")
st.title("📊 SIAM Commodity Price Intelligence Dashboard")

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

@st.cache_data
def load_all_saved_pdfs():
    """Reads all PDFs saved in the local data directory to persist data for all users."""
    all_data = []
    pdf_files = glob.glob(os.path.join(DATA_DIR, "*.pdf"))
    
    for pdf_file in pdf_files:
        df = process_siam_pdf(pdf_file)
        all_data.append(df)
        
    if all_data:
        combined_df = pd.concat(all_data).drop_duplicates(subset=['Commodity', 'Date']).sort_values(['Commodity', 'Date'])
        return combined_df
    return pd.DataFrame()

# Initialize session state with saved data
if 'dataset' not in st.session_state or st.session_state['dataset'].empty:
    st.session_state['dataset'] = load_all_saved_pdfs()

# --- Sidebar: File Upload & Filtering ---
with st.sidebar:
    st.header("1. Upload Data")
    st.caption("Files uploaded here are saved permanently for all users viewing this URL.")
    uploaded_files = st.file_uploader("Upload SIAM PDFs", type=['pdf'], accept_multiple_files=True)
    
    if uploaded_files:
        for file in uploaded_files:
            file_path = os.path.join(DATA_DIR, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
                
        st.cache_data.clear()
        st.session_state['dataset'] = load_all_saved_pdfs()
        st.success(f"Successfully saved and processed {len(uploaded_files)} file(s).")
        st.rerun()

    st.divider()
    
    st.header("2. Dashboard Filters")
    if not st.session_state['dataset'].empty:
        df = st.session_state['dataset']
        
        # --- Time Period LOV (Month & Year) ---
        st.subheader("Time Period")
        unique_dates = sorted(df['Date'].dt.date.unique())
        date_labels = [d.strftime("%B %Y") for d in unique_dates]
        
        col_start, col_end = st.columns(2)
        with col_start:
            start_date_label = st.selectbox("From", options=date_labels, index=0)
        with col_end:
            end_date_label = st.selectbox("To", options=date_labels, index=len(date_labels)-1)
            
        start_date = pd.to_datetime(start_date_label).date()
        end_date = pd.to_datetime(end_date_label).date()
        
        st.divider()
        
        # --- Commodity LOV (Multiple Choice) ---
        st.subheader("Commodity Selection")
        main_categories = sorted(df['Main Category'].unique().tolist())
        
        # Multiselect for Main Category (Defaults to everything selected)
        selected_main_categories = st.multiselect("Select Main Commodity", options=main_categories, default=main_categories)
        
        # Dynamically populate Sub-Commodities based on Main Categories chosen
        if selected_main_categories:
            sub_commodities = df[df['Main Category'].isin(selected_main_categories)]['Commodity'].unique().tolist()
        else:
            sub_commodities = df['Commodity'].unique().tolist()
            
        # Multiselect for Sub Commodity (Defaults to everything selected)
        selected_sub_commodities = st.multiselect("Select Sub Commodity (LOV)", options=sub_commodities, default=sub_commodities)

# --- Main Dashboard Area ---
if st.session_state['dataset'].empty:
    st.info("No data found. Please upload a SIAM Commodity PDF in the sidebar to generate the dashboard.")
else:
    if start_date > end_date:
        st.error("Error: 'From' date cannot be after 'To' date.")
    elif not selected_sub_commodities:
        st.warning("Please select at least one Sub Commodity from the sidebar.")
    else:
        # STRICT FILTERING: Explicitly filter data based on user dropdowns
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date) & (df['Commodity'].isin(selected_sub_commodities))
        filtered_df = df.loc[mask]
        
        if filtered_df.empty:
            st.warning("No data available for the selected time period and commodities.")
        else:
            for commodity in selected_sub_commodities:
                c_df = filtered_df[filtered_df['Commodity'] == commodity].copy()
                c_df.reset_index(drop=True, inplace=True)
                
                # Skip if the user's date filter hid all data for this specific commodity
                if c_df.empty:
                    continue
                    
                unit = c_df['Unit'].iloc[0]
                main_cat = c_df['Main Category'].iloc[0]
                
                st.subheader(f"{commodity} ({main_cat})")
                
                # BI Calculations
                peak_idx = c_df['Price'].idxmax()
                min_idx = c_df['Price'].idxmin()
                
                peak_val = c_df.loc[peak_idx, 'Price']
                peak_date = c_df.loc[peak_idx, 'Date'].strftime('%b %Y')
                
                min_val = c_df.loc[min_idx, 'Price']
                min_date = c_df.loc[min_idx, 'Date'].strftime('%b %Y')
                
                c_df.set_index('Date', inplace=True)
                q_df = c_df.resample('QE').mean(numeric_only=True)
                
                if len(q_df) >= 2:
                    latest_q_val = q_df['Price'].iloc[-1]
                    prev_q_val = q_df['Price'].iloc[-2]
                    qoq_pct = ((latest_q_val - prev_q_val) / prev_q_val) * 100
                    qoq_abs = latest_q_val - prev_q_val
                else:
                    qoq_pct, qoq_abs = 0.0, 0.0
                    
                c_df.reset_index(inplace=True)
                
                # Render Metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(label="Latest Price", value=f"{c_df['Price'].iloc[-1]:,.2f} {unit}", 
                              delta=f"{qoq_pct:.2f}% QoQ ({qoq_abs:+,.2f})")
                with col2:
                    st.metric(label="Peak Value", value=f"{peak_val:,.2f} {unit}", help=f"Occurred in {peak_date}")
                    st.caption(f"📅 *{peak_date}*")
                with col3:
                    st.metric(label="Minimum Value", value=f"{min_val:,.2f} {unit}", help=f"Occurred in {min_date}")
                    st.caption(f"📅 *{min_date}*")
                    
                # Interactive Graph
                fig = px.line(c_df, x='Date', y='Price', markers=True, 
                              title=f"Price Trend: {commodity}",
                              labels={"Price": f"Price ({unit})", "Date": "Time Period"})
                              
                fig.update_traces(line_color='#1f77b4', hovertemplate="<b>Date:</b> %{x|%b %Y}<br><b>Price:</b> %{y:,.2f}")
                fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0))
                
                st.plotly_chart(fig, use_container_width=True)
                st.divider()
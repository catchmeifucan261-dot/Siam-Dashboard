import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
from extractor import process_siam_pdf

# --- 1. Page Configuration & Custom Compact Aesthetics ---
st.set_page_config(page_title="SIAM Commodity Monitor", layout="wide")

# Custom CSS: Reduce font sizes across headings, metrics, tables, and UI controls
st.markdown("""
<style>
    /* Base typography */
    html, body, [class*="css"], .stMarkdown {
        font-size: 13px !important;
    }
    h1 { font-size: 20px !important; font-weight: 700 !important; margin-bottom: 0.5rem !important; }
    h2 { font-size: 16px !important; font-weight: 600 !important; margin-top: 0.5rem !important; }
    h3 { font-size: 14px !important; font-weight: 600 !important; margin-top: 0.4rem !important; }
    
    /* Compact Metrics */
    [data-testid="stMetricValue"] {
        font-size: 17px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 11px !important;
        color: #555 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 11px !important;
    }
    
    /* Compact DataFrames & Tables */
    [data-testid="stDataFrame"] {
        font-size: 12px !important;
    }
    
    /* Tighten vertical spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 SIAM Commodity Price Intelligence Dashboard")

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

@st.cache_data
def load_all_saved_pdfs():
    """Reads all PDFs saved in the local data directory for persistent access."""
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

# --- 2. Sidebar Controls ---
with st.sidebar:
    st.header("1. Upload Monitor Reports")
    st.caption("PDFs uploaded here are permanently stored in the repository.")
    uploaded_files = st.file_uploader("Upload SIAM PDFs", type=['pdf'], accept_multiple_files=True)
    
    if uploaded_files:
        for file in uploaded_files:
            file_path = os.path.join(DATA_DIR, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
                
        st.cache_data.clear()
        st.session_state['dataset'] = load_all_saved_pdfs()
        st.success(f"Stored & processed {len(uploaded_files)} file(s).")
        st.rerun()

    st.divider()
    
    st.header("2. Filtering Controls")
    if not st.session_state['dataset'].empty:
        df = st.session_state['dataset']
        
        # --- Time Period Range Selection ---
        st.subheader("Time Range")
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
        
        # --- Commodity Multi-Select Lists of Values (LOV) ---
        st.subheader("Commodity Hierarchy")
        main_categories = sorted(df['Main Category'].unique().tolist())
        selected_main_categories = st.multiselect("Select Category", options=main_categories, default=main_categories)
        
        if selected_main_categories:
            sub_commodities = sorted(df[df['Main Category'].isin(selected_main_categories)]['Commodity'].unique().tolist())
        else:
            sub_commodities = sorted(df['Commodity'].unique().tolist())
            
        selected_sub_commodities = st.multiselect("Select Sub-Commodity (LOV)", options=sub_commodities, default=sub_commodities)

# --- 3. Main Dashboard Display ---
if st.session_state['dataset'].empty:
    st.info("No data found. Upload a SIAM Monthly Monitor PDF in the sidebar to populate the dashboard.")
else:
    if start_date > end_date:
        st.error("Error: 'From' date cannot be later than 'To' date.")
    elif not selected_sub_commodities:
        st.warning("Select at least one Sub-Commodity from the sidebar.")
    else:
        # Filter global dataframe by date range & selected commodities
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date) & (df['Commodity'].isin(selected_sub_commodities))
        filtered_df = df.loc[mask].copy()
        
        if filtered_df.empty:
            st.warning("No data points available for the selected range and commodities.")
        else:
            # --- Dedicated Export Center with Year/Month Dropdowns ---
            with st.expander("📥 Download Center (Export Monthly Historical Data)", expanded=False):
                st.write("**Filter and export structured monthly prices:**")
                
                exp_col1, exp_col2, exp_col3 = st.columns([2, 2, 2])
                with exp_col1:
                    available_years = sorted(list(set(filtered_df['Date'].dt.year.tolist())), reverse=True)
                    selected_exp_years = st.multiselect("Filter Years", options=available_years, default=available_years)
                with exp_col2:
                    month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                    selected_exp_months = st.multiselect("Filter Months", options=month_names, default=month_names)
                
                # Apply export-specific filter
                exp_mask = (filtered_df['Date'].dt.year.isin(selected_exp_years)) & (filtered_df['Date'].dt.strftime('%B').isin(selected_exp_months))
                export_subset = filtered_df.loc[exp_mask].copy()
                
                export_subset['Month-Year'] = export_subset['Date'].dt.strftime('%b-%Y')
                export_display = export_subset[['Commodity', 'Main Category', 'Month-Year', 'Price', 'Unit']].sort_values(['Commodity', 'Month-Year'])
                
                with exp_col3:
                    st.write("")
                    st.write("")
                    csv_data = export_display.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="⬇️ Download CSV File",
                        data=csv_data,
                        file_name="siam_commodity_data_export.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                st.caption(f"Ready to export {len(export_display)} monthly records.")

            st.divider()

            # --- Individual Commodity Intelligence Views ---
            for commodity in selected_sub_commodities:
                c_df = filtered_df[filtered_df['Commodity'] == commodity].copy()
                c_df.sort_values('Date', inplace=True)
                c_df.reset_index(drop=True, inplace=True)
                
                if c_df.empty:
                    continue
                    
                unit = c_df['Unit'].iloc[0]
                main_cat = c_df['Main Category'].iloc[0]
                
                # Header
                st.markdown(f"### {commodity} <span style='font-size:12px; color:gray; font-weight:normal;'>({main_cat})</span>", unsafe_allow_html=True)
                
                # Intelligence Calculations
                peak_idx = c_df['Price'].idxmax()
                min_idx = c_df['Price'].idxmin()
                
                peak_val = c_df.loc[peak_idx, 'Price']
                peak_date = c_df.loc[peak_idx, 'Date'].strftime('%b %Y')
                
                min_val = c_df.loc[min_idx, 'Price']
                min_date = c_df.loc[min_idx, 'Date'].strftime('%b %Y')
                
                # Quarter-on-Quarter Calculation
                c_df_temp = c_df.set_index('Date')
                q_df = c_df_temp.resample('QE').mean(numeric_only=True)
                
                if len(q_df) >= 2:
                    latest_q_val = q_df['Price'].iloc[-1]
                    prev_q_val = q_df['Price'].iloc[-2]
                    qoq_pct = ((latest_q_val - prev_q_val) / prev_q_val) * 100
                    qoq_abs = latest_q_val - prev_q_val
                else:
                    qoq_pct, qoq_abs = 0.0, 0.0

                # Summary Metric Bar
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(label="Latest Price", value=f"{c_df['Price'].iloc[-1]:,.2f} {unit}", 
                              delta=f"{qoq_pct:.2f}% QoQ ({qoq_abs:+,.2f})")
                with col2:
                    st.metric(label="Peak Value", value=f"{peak_val:,.2f} {unit}")
                    st.caption(f"📅 Peak: {peak_date}")
                with col3:
                    st.metric(label="Minimum Value", value=f"{min_val:,.2f} {unit}")
                    st.caption(f"📅 Min: {min_date}")
                with col4:
                    st.metric(label="Data Points Visible", value=f"{len(c_df)} Months")
                    st.caption(f"Range: {c_df['Date'].min().strftime('%b %y')} - {c_df['Date'].max().strftime('%b %y')}")

                # Compact Interactive Plotly Chart
                fig = px.line(
                    c_df, 
                    x='Date', 
                    y='Price', 
                    markers=True,
                    labels={"Price": f"Price ({unit})", "Date": "Month"}
                )
                
                # Styling adjustments: smaller fonts, tight margins, legible ticks
                fig.update_traces(
                    line_color='#1f77b4', 
                    line_width=2,
                    marker=dict(size=4.5),
                    hovertemplate="<b>%{x|%b %Y}</b><br>Price: %{y:,.2f} " + unit + "<extra></extra>"
                )
                
                fig.update_layout(
                    font=dict(size=10, color="#333"),
                    height=280,
                    margin=dict(l=10, r=10, t=20, b=10),
                    hovermode="x unified",
                    xaxis=dict(
                        showgrid=True,
                        gridcolor="#eee",
                        tickformat="%b-%y",
                        tickangle=-40,
                        tickfont=dict(size=9.5),
                        nticks=len(c_df)
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="#eee",
                        tickfont=dict(size=9.5),
                        title=dict(text=f"{unit}", font=dict(size=10))
                    )
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Monthly Breakdown Table
                with st.expander(f"📋 View Monthly Data Table: {commodity}", expanded=False):
                    table_df = c_df[['Date', 'Price']].copy()
                    table_df['Month-Year'] = table_df['Date'].dt.strftime('%B %Y')
                    table_df['Price Formatted'] = table_df['Price'].apply(lambda x: f"{x:,.2f} {unit}")
                    
                    # MoM Price Change
                    table_df['MoM Change (Abs)'] = table_df['Price'].diff()
                    table_df['MoM Change (%)'] = table_df['Price'].pct_change() * 100
                    
                    table_display = table_df[['Month-Year', 'Price Formatted', 'MoM Change (%)', 'MoM Change (Abs)']].copy()
                    table_display['MoM Change (%)'] = table_display['MoM Change (%)'].apply(
                        lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-"
                    )
                    table_display['MoM Change (Abs)'] = table_display['MoM Change (Abs)'].apply(
                        lambda x: f"{x:+,.2f}" if pd.notnull(x) else "-"
                    )
                    
                    st.dataframe(table_display, use_container_width=True, hide_index=True)

                st.divider()
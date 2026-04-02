import streamlit as st
import pandas as pd
import requests
from io import StringIO, BytesIO
from datetime import datetime, timedelta
import plotly.express as px

###Today is 2026-04-02-21

st.set_page_config(
    page_title="OPS Jobs Explorer",
    page_icon="💼",
    layout="wide",
)

# Replace with your GitHub personal access token
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]

# GitHub repository details
REPO_OWNER = st.secrets["REPO_OWNER"]
REPO_NAME = st.secrets["REPO_NAME"]
BRANCH = st.secrets["BRANCH"]
DIRECTORY = st.secrets["DIRECTORY"]

# URL of the CSV file in the private repo
CURRENT_CSV_URL = st.secrets["CURRENT_CSV_URL"]
RECENT_CSV_URL = st.secrets["RECENT_CSV_URL"]
HISTORICAL_CSV_URL = st.secrets["HISTORICAL_CSV_URL"]
CURRENT_EXT_URL = st.secrets["CURRENT_EXT_URL"]
RECENT_EXT_URL = st.secrets["RECENT_EXT_URL"]
HISTORICAL_EXT_URL = st.secrets["HISTORICAL_EXT_URL"]

# Salary cutoffs
MIN_SALARY = st.secrets["MIN_SALARY"]
MAX_SALARY = st.secrets["MAX_SALARY"]


# Function to fetch the list of files in the directory
def fetch_file_list(repo_owner, repo_name, branch, directory, token):
    url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{directory}?ref={branch}'
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to fetch the file list from GitHub")
        return None


# Function to fetch the CSV file from GitHub
def fetch_csv_from_github(url, token):
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return StringIO(response.text)
    else:
        st.error(f"Failed to fetch the CSV file from GitHub: {url}")
        return None


# Function to fetch the parquet file from GitHub
def fetch_parquet_from_github(url, token):
    headers = {'Authorization': f'token {token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return BytesIO(response.content)
    else:
        print(f"Failed to fetch the Parquet file from GitHub: {url}")
        return None


def calculate_annual_salary(salary_str, type):
    """Parse a freeform OPS salary string and return an annualized float.

    Handles Per Year, Per Annum, Per Month, Per Week, and Per Hour rates.
    Strips the '(MplusM)' suffix before parsing.

    Args:
        salary_str: Raw salary string from the data source (e.g. "$60,000.00 - $80,000.00 Per Year").
        type: 'Min' to return the lower bound, 'Max' to return the upper bound.

    Returns:
        Annualized salary as a float, or None if parsing fails.
    """
    if type == 'Min':
        try:
            salary_str = salary_str.replace(' (MplusM)', '')
            salary_range = salary_str.replace('$', '').replace(',', '').split(' Per')[0].split(' - ')
            if 'Per Year'.lower() in salary_str.lower():
                return float(salary_range[0])
            elif 'Per Annum'.lower() in salary_str.lower():
                return float(salary_range[0])
            elif 'Per Month'.lower() in salary_str.lower():
                return float(salary_range[0]) * 12
            elif 'Per Week'.lower() in salary_str.lower():
                return float(salary_range[0]) * 52
            elif 'Per Hour'.lower() in salary_str.lower():
                return float(salary_range[0]) * 36.25 * 52
        except Exception:
            return None
    elif type == 'Max':
        try:
            salary_str = salary_str.replace(' (MplusM)', '')
            salary_range = salary_str.replace('$', '').replace(',', '').split(' Per')[0].split(' - ')
            if 'Per Year'.lower() in salary_str.lower():
                return float(salary_range[1])
            elif 'Per Annum'.lower() in salary_str.lower():
                return float(salary_range[1])
            elif 'Per Month'.lower() in salary_str.lower():
                return float(salary_range[1]) * 12
            elif 'Per Week'.lower() in salary_str.lower():
                return float(salary_range[1]) * 52
            elif 'Per Hour'.lower() in salary_str.lower():
                return float(salary_range[1]) * 36.25 * 52
        except Exception:
            return None
    return None


def adjust_salary_with_year(salary, salary_year):
    """Adjust a historical salary to present-day value using Canadian CPI data.

    Uses average annual CPI (non-seasonally adjusted) for Canada from 2008 onward.
    If the salary year is not in the CPI table the original value is returned unchanged.

    Args:
        salary: The nominal salary to adjust.
        salary_year: The year the salary was set (int or castable to int).

    Returns:
        CPI-adjusted salary rounded to two decimal places, or the original salary
        if no adjustment is needed or possible.
    """
    # Average annual CPI for Canada, non-seasonally adjusted (2008-2025)
    # Note: 2025 figure is an average of Jan-Nov 2025 (not final)
    cpi_data = {
        2008: 114.1, 2009: 114.4, 2010: 116.5, 2011: 119.9, 2012: 121.7,
        2013: 122.8, 2014: 125.2, 2015: 126.6, 2016: 128.4, 2017: 130.4,
        2018: 133.4, 2019: 136.0, 2020: 137.0, 2021: 141.6, 2022: 151.2,
        2023: 157.1, 2024: 160.9, 2025: 164.1,
    }

    salary_year = int(salary_year)
    salary = float(salary)

    if salary_year not in cpi_data:
        return salary

    current_year = datetime.now().year
    if salary_year == current_year:
        return salary

    base_cpi = cpi_data[salary_year]
    current_cpi = cpi_data[max(cpi_data.keys())]
    adjusted_salary = salary * (current_cpi / base_cpi)
    return round(adjusted_salary, 2)


def apply_filter(df, conditions):
    """Chain a list of boolean filter conditions with AND / OR / NOT logic.

    Args:
        df: The source DataFrame to filter.
        conditions: List of dicts with keys 'filter' (boolean Series) and
                    'logic' ('AND', 'OR', or 'NOT').  The first condition's
                    'logic' value is ignored (always used as the base).

    Returns:
        Filtered DataFrame.
    """
    condition = conditions[0]['filter']
    for i in range(1, len(conditions)):
        if conditions[i]['logic'] == 'AND':
            condition &= conditions[i]['filter']
        elif conditions[i]['logic'] == 'OR':
            condition |= conditions[i]['filter']
        elif conditions[i]['logic'] == 'NOT':
            condition &= ~conditions[i]['filter']
    return df[condition]


@st.cache_data
def load_data(ttl=3600):
    """Fetch and combine job data from three temporal tiers (current/recent/historical).

    Data is pulled from a private GitHub repository as CSV and Parquet files.
    Core job fields and extended (EXT) fields are loaded separately then joined
    on Job ID.  Salary strings are normalised to annual figures and closing dates
    are parsed to both a formatted string and a datetime object.

    Args:
        ttl: Cache time-to-live in seconds (not passed to the decorator directly;
             changing this value busts the cache).

    Returns:
        DataFrame with columns: Job ID, Job Title, Job Code, Organization,
        Division, Salary Min, Salary Max, Location, Address, Closing Date,
        Closing Date Object.
    """
    csv_file = fetch_csv_from_github(CURRENT_CSV_URL, GITHUB_TOKEN)
    new_job_df = pd.read_csv(csv_file)

    csv_file_recent = fetch_csv_from_github(RECENT_CSV_URL, GITHUB_TOKEN)
    recent_job_df = pd.read_csv(csv_file_recent)

    csv_file_historical = fetch_csv_from_github(HISTORICAL_CSV_URL, GITHUB_TOKEN)
    historical_job_df = pd.read_csv(csv_file_historical)

    EXT_file = fetch_parquet_from_github(CURRENT_EXT_URL, GITHUB_TOKEN)
    new_EXT_df = pd.read_parquet(EXT_file)

    EXT_file_recent = fetch_csv_from_github(RECENT_EXT_URL, GITHUB_TOKEN)
    recent_EXT_df = pd.read_csv(EXT_file_recent)

    EXT_file_historical = fetch_parquet_from_github(HISTORICAL_EXT_URL, GITHUB_TOKEN)
    historical_EXT_df = pd.read_parquet(EXT_file_historical)

    combined_job_df = pd.concat([recent_job_df, new_job_df, historical_job_df])
    combined_job_df = combined_job_df.loc[:, ~combined_job_df.columns.str.contains('^Unnamed')].reset_index(drop=True)

    combined_EXT_df = pd.concat([recent_EXT_df, new_EXT_df, historical_EXT_df])
    combined_EXT_df = combined_EXT_df.loc[:, ~combined_EXT_df.columns.str.contains('^Unnamed')].reset_index(drop=True)

    combined_df = pd.merge(combined_job_df, combined_EXT_df, on='Job ID', how='left').drop_duplicates(subset='Job ID')
    combined_df = combined_df.loc[:, ~combined_df.columns.str.contains('^Unnamed')].reset_index(drop=True)

    combined_df['Salary Min'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Min'))
    combined_df['Salary Max'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Max'))

    combined_df['Closing Date Object'] = pd.to_datetime(combined_df['Closing Date'], errors='coerce')
    combined_df['Closing Date'] = combined_df['Closing Date Object'].dt.strftime('%Y-%m-%d')

    combined_df['Job ID'] = combined_df['Job ID'].apply(lambda x: str(x).replace(",", ""))

    del new_job_df, recent_job_df, historical_job_df
    del new_EXT_df, recent_EXT_df, historical_EXT_df
    del combined_job_df, combined_EXT_df

    columns = [
        'Job ID', 'Job Title', 'Job Code', 'Organization', 'Division',
        'Salary Min', 'Salary Max', 'Location', 'Address',
        'Closing Date', 'Closing Date Object',
    ]
    return combined_df[columns]


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

combined_df = load_data()

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title("💼 OPS Jobs Explorer")
st.caption(
    "Browse Ontario Public Service job postings from "
    "[gojobs.gov.on.ca](https://www.gojobs.gov.on.ca). "
    "Use the sidebar filters to narrow results, then click **Open** on any row to view the full posting."
)
st.divider()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

conditions = []  # Job title boolean filter conditions accumulated here

with st.sidebar:
    st.header("🔍 Filter Jobs")

    # ── Date & Salary ────────────────────────────────────────────────────────
    st.subheader("📅 Date & Salary")

    salary_filter = st.slider(
        "Annual Salary Range",
        min_value=0,
        max_value=200000,
        value=(MIN_SALARY, MAX_SALARY),
        step=1000,
        format="$%d",
        help="Filter by annualised salary range. Hourly/weekly/monthly rates are converted automatically.",
    )

    start_date, end_date = st.date_input(
        "Closing Date Range",
        value=(datetime.today(), datetime.today() + timedelta(weeks=4)),
        min_value=combined_df['Closing Date Object'].min(),
        help="Show only postings whose closing date falls within this window.",
    )

    # ── Organization & Location ──────────────────────────────────────────────
    st.subheader("🏢 Organization & Location")

    organizations = sorted(combined_df['Organization'].dropna().unique())
    organization_filter = st.selectbox(
        "Organization",
        ["All"] + organizations,
        help="Filter to a specific ministry or agency.",
    )

    location_filter = st.text_input(
        "Location",
        "",
        placeholder="e.g. Toronto",
        help="Case-insensitive substring match on the Location field.",
    ).lower()

    # ── Job Title Search ─────────────────────────────────────────────────────
    st.subheader("🔎 Job Title Search")

    num_filters = st.number_input(
        "Number of Title Filters",
        min_value=1,
        max_value=5,
        value=1,
        step=1,
        help="Add up to 5 keyword filters combinable with AND / OR / NOT logic.",
    )

    for i in range(num_filters):
        if i > 0:
            logic_operator = st.selectbox(
                f"Operator for Filter {i + 1}",
                ('AND', 'OR', 'NOT'),
                key=f"operator_{i + 1}",
                help="AND = must also match | OR = either match | NOT = must NOT match",
            )
        else:
            logic_operator = 'AND'

        filter_text = st.text_input(
            f"Keyword {i + 1}",
            "",
            placeholder="e.g. analyst",
            key=f"title_filter_{i}",
        )

        if filter_text:
            filter_condition = combined_df['Job Title'].str.lower().str.contains(
                filter_text.lower(), case=False, na=False
            )
            conditions.append({'filter': filter_condition, 'logic': logic_operator})

    # ── Display Options ──────────────────────────────────────────────────────
    st.subheader("⚙️ Display Options")

    show_EXT_data = st.checkbox(
        'Show Extended Data',
        value=False,
        help="Reveal Division, Address, and Job Code columns and their filters.",
    )

    if show_EXT_data:
        st.markdown("**Extended Filters**")
        division_filter = st.text_input(
            "Division",
            "",
            placeholder="e.g. Digital",
            help="Case-insensitive substring match on the Division field.",
        ).lower()
        address_filter = st.text_input(
            "Address",
            "",
            placeholder="e.g. Bay St",
            help="Case-insensitive substring match on the Address field.",
        ).lower()
        job_code_filter = st.text_input(
            "Job Code",
            "",
            placeholder="e.g. 17120",
            help="Case-insensitive substring match on the Job Code field.",
        ).lower()

    show_restricted = st.checkbox(
        'Show TDA / Restricted Jobs Only',
        value=False,
        help="Toggle to see only postings restricted to existing OPS employees (TDA).",
    )

    show_int_URL = st.checkbox(
        'Use Internal URLs',
        value=False,
        help="Switch job links to the internal OPS intranet (intra.employees.careers.gov.on.ca).",
    )

    show_CPI_adjusted_salary = st.checkbox(
        'Inflation-Adjusted Salaries',
        value=False,
        help="Adjust historical salaries to present-day purchasing power using Canadian CPI data (2008-2025).",
    )

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

if show_EXT_data:
    filtered_df = combined_df[
        (combined_df['Closing Date Object'] >= pd.to_datetime(start_date)) &
        (combined_df['Closing Date Object'] <= pd.to_datetime(end_date)) &
        (combined_df['Salary Min'] >= salary_filter[0]) &
        (combined_df['Salary Max'] <= salary_filter[1]) &
        ((combined_df['Organization'] == organization_filter) | (organization_filter == "All")) &
        (combined_df['Location'].str.lower().str.contains(location_filter)) &
        (combined_df['Division'].str.lower().str.contains(division_filter)) &
        (combined_df['Address'].str.lower().str.contains(address_filter)) &
        (combined_df['Job Code'].str.lower().str.contains(job_code_filter))
    ]
else:
    filtered_df = combined_df[
        (combined_df['Closing Date Object'] >= pd.to_datetime(start_date)) &
        (combined_df['Closing Date Object'] <= pd.to_datetime(end_date)) &
        (combined_df['Salary Min'] >= salary_filter[0]) &
        (combined_df['Salary Max'] <= salary_filter[1]) &
        ((combined_df['Organization'] == organization_filter) | (organization_filter == "All")) &
        (combined_df['Location'].str.lower().str.contains(location_filter))
    ]

if conditions:
    filtered_df = apply_filter(filtered_df, conditions)

# TDA / restricted toggle
if show_restricted:
    filtered_df = filtered_df[filtered_df['Job Title'].str.lower().str.contains('restricted to')]
else:
    filtered_df = filtered_df[~filtered_df['Job Title'].str.lower().str.contains('restricted to')]

# Build job links
if show_int_URL:
    filtered_df = filtered_df.copy()
    filtered_df['Link'] = filtered_df['Job ID'].apply(
        lambda x: f"https://intra.employees.careers.gov.on.ca/Preview.aspx?JobID={x}"
    )
else:
    filtered_df = filtered_df.copy()
    filtered_df['Link'] = filtered_df['Job ID'].apply(
        lambda x: f"https://www.gojobs.gov.on.ca/Preview.aspx?Language=English&JobID={x}"
    )

# Inflation adjustment
if show_CPI_adjusted_salary:
    filtered_df['Closing Year'] = filtered_df['Closing Date Object'].dt.year
    filtered_df['Salary Min'] = filtered_df.apply(
        lambda x: adjust_salary_with_year(x['Salary Min'], x['Closing Year']), axis=1
    )
    filtered_df['Salary Max'] = filtered_df.apply(
        lambda x: adjust_salary_with_year(x['Salary Max'], x['Closing Year']), axis=1
    )

# Job ID picker — rendered after main filters so the choices reflect current results
with st.sidebar:
    st.subheader("🆔 Pinpoint by Job ID")
    job_ids = filtered_df['Job ID'].unique()
    job_id_filter = st.multiselect(
        "Job ID",
        job_ids,
        default=job_ids,
        help="Select one or more specific Job IDs to narrow the table to those postings only.",
    )

filtered_df = filtered_df[filtered_df['Job ID'].isin(job_id_filter)]

# ---------------------------------------------------------------------------
# Metrics row
# ---------------------------------------------------------------------------

today = pd.Timestamp(datetime.today().date())
closing_soon = int(
    (filtered_df['Closing Date Object'] <= today + pd.Timedelta(days=7)).sum()
)
avg_salary_min = filtered_df['Salary Min'].mean()
avg_salary_max = filtered_df['Salary Max'].mean()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Jobs Found", len(filtered_df))
m2.metric(
    "Avg Salary Min",
    f"${avg_salary_min:,.0f}" if pd.notna(avg_salary_min) else "N/A",
)
m3.metric(
    "Avg Salary Max",
    f"${avg_salary_max:,.0f}" if pd.notna(avg_salary_max) else "N/A",
)
m4.metric("Closing Within 7 Days", closing_soon)

st.divider()

# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------

if show_EXT_data:
    column_order = [
        'Job ID', 'Job Title', 'Job Code', 'Organization', 'Division',
        'Salary Min', 'Salary Max', 'Location', 'Address', 'Closing Date', 'Link',
    ]
else:
    column_order = [
        'Job ID', 'Job Title', 'Organization',
        'Salary Min', 'Salary Max', 'Location', 'Closing Date', 'Link',
    ]

display_df = filtered_df[column_order].sort_values(
    by=['Closing Date', 'Salary Min'], ascending=[True, True]
)

if display_df.empty:
    st.info("No jobs match your current filters. Try widening the date range or salary slider.")
else:
    # Download button
    csv_bytes = display_df.drop(columns=['Link']).to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Download results as CSV",
        data=csv_bytes,
        file_name="ops_jobs.csv",
        mime="text/csv",
        help="Downloads the current filtered results (without the URL column).",
    )

    st.dataframe(
        display_df,
        column_config={
            "Link": st.column_config.LinkColumn("URL", display_text="Open"),
            "Salary Min": st.column_config.NumberColumn("Salary Min", format="$%d"),
            "Salary Max": st.column_config.NumberColumn("Salary Max", format="$%d"),
        },
        hide_index=True,
        use_container_width=True,
    )

    # ── Charts ───────────────────────────────────────────────────────────────
    st.subheader("📊 Visual Summaries")

    chart_col1, chart_col2, chart_col3 = st.columns(3)

    with chart_col1:
        filtered_df['Date'] = filtered_df['Closing Date Object'].dt.strftime('%Y-%m-%d')
        fig_dates = px.histogram(
            filtered_df,
            x='Date',
            labels={'Date': 'Closing Date', 'count': 'Jobs'},
            title="Jobs by Closing Date",
            histfunc='count',
            template='plotly',
        )
        fig_dates.update_xaxes(tickformat="%Y-%m-%d", title="Closing Date")
        fig_dates.update_yaxes(title="Number of Jobs")
        fig_dates.update_layout(showlegend=False)
        st.plotly_chart(fig_dates, use_container_width=True)

    with chart_col2:
        salary_data = filtered_df['Salary Min'].dropna()
        fig_salary = px.histogram(
            salary_data,
            x=salary_data,
            nbins=30,
            labels={'x': 'Annual Salary Min', 'count': 'Frequency'},
            title="Salary Distribution (Min)",
            template='plotly',
        )
        fig_salary.update_layout(
            xaxis_title="Annual Salary (Min)",
            yaxis_title="Frequency",
            bargap=0.1,
            showlegend=False,
        )
        st.plotly_chart(fig_salary, use_container_width=True)

    with chart_col3:
        org_counts = (
            filtered_df['Organization']
            .value_counts()
            .head(10)
            .reset_index()
        )
        org_counts.columns = ['Organization', 'Count']
        fig_orgs = px.bar(
            org_counts,
            x='Count',
            y='Organization',
            orientation='h',
            title="Top 10 Organizations",
            template='plotly',
            labels={'Count': 'Number of Jobs', 'Organization': ''},
        )
        fig_orgs.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig_orgs, use_container_width=True)

import streamlit as st
import streamlit_authenticator as stauth
from datetime import datetime, timedelta
import pandas as pd
import requests
from io import StringIO, BytesIO
import plotly.express as px

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(layout="wide", page_title="OPS Jobs Data")

# =========================
# AUTHENTICATION
# =========================
# Load authentication config from secrets
config = {
    'credentials': {
        'usernames': {
            user: {
                'name': st.secrets['credentials']['usernames'][user]['name'],
                'password': st.secrets['credentials']['usernames'][user]['password'],
                'totp': st.secrets['credentials']['usernames'][user]['totp']
            }
            for user in st.secrets['credentials']['usernames']
        }
    },
    'cookie': {
        'name': st.secrets['cookie']['name'],
        'key': st.secrets['cookie']['key'],
        'expiry_days': st.secrets['cookie']['expiry_days']
    },
    'preauthorized': {'emails': []}
}

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status is False:
    st.error("Username/password is incorrect")
elif authentication_status is None:
    st.warning("Please enter your username and password")
elif authentication_status:

    # Verify 2FA
    totp_code = st.text_input("Enter your 6-digit authentication code", type="password")
    if st.button("Verify 2FA"):
        if stauth.Hasher.verify_totp(config['credentials']['usernames'][username]['totp'], totp_code):
            st.success(f"Welcome, {name}!")
            authenticator.logout("Logout", "sidebar")

            # =========================
            # GITHUB CONFIG
            # =========================
            GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
            REPO_OWNER = st.secrets["REPO_OWNER"]
            REPO_NAME = st.secrets["REPO_NAME"]
            BRANCH = st.secrets["BRANCH"]
            CURRENT_CSV_URL = st.secrets["CURRENT_CSV_URL"]
            RECENT_CSV_URL = st.secrets["RECENT_CSV_URL"]
            HISTORICAL_CSV_URL = st.secrets["HISTORICAL_CSV_URL"]
            CURRENT_EXT_URL = st.secrets["CURRENT_EXT_URL"]
            RECENT_EXT_URL = st.secrets["RECENT_EXT_URL"]
            HISTORICAL_EXT_URL = st.secrets["HISTORICAL_EXT_URL"]
            MIN_SALARY = st.secrets["MIN_SALARY"]
            MAX_SALARY = st.secrets["MAX_SALARY"]

            # =========================
            # DATA FETCHING FUNCTIONS
            # =========================
            def fetch_csv_from_github(url, token):
                headers = {'Authorization': f'token {token}'}
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    return StringIO(response.text)
                else:
                    st.error(f"Failed to fetch CSV: {url}")
                    return None

            def fetch_parquet_from_github(url, token):
                headers = {'Authorization': f'token {token}'}
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    return BytesIO(response.content)
                else:
                    st.error(f"Failed to fetch Parquet: {url}")
                    return None

            def calculate_annual_salary(salary_str, typ):
                if not isinstance(salary_str, str):
                    return None
                salary_str = salary_str.replace(' (MplusM)', '')
                try:
                    salary_range = salary_str.replace('$', '').replace(',', '').split(' Per')[0].split(' - ')
                    value = float(salary_range[0 if typ == 'Min' else 1])
                    if 'per year' in salary_str.lower() or 'per annum' in salary_str.lower():
                        return value
                    elif 'per month' in salary_str.lower():
                        return value * 12
                    elif 'per week' in salary_str.lower():
                        return value * 52
                    elif 'per hour' in salary_str.lower():
                        return value * 36.25 * 52
                except:
                    return None
                return None

            def adjust_salary_with_year(salary, year):
                cpi_data = {
                    2008: 114.1, 2009: 114.4, 2010: 116.5, 2011: 119.9, 2012: 121.7,
                    2013: 122.8, 2014: 125.2, 2015: 126.6, 2016: 128.4, 2017: 130.4,
                    2018: 133.4, 2019: 136.0, 2020: 137.0, 2021: 141.6, 2022: 151.2,
                    2023: 157.1, 2024: 160.6
                }
                if year not in cpi_data:
                    return salary
                current_cpi = cpi_data[max(cpi_data)]
                return round(salary * (current_cpi / cpi_data[year]), 2)

            @st.cache_data(ttl=3600)
            def load_data():
                # Fetch all CSV/Parquet files
                new_job_df = pd.read_csv(fetch_csv_from_github(CURRENT_CSV_URL, GITHUB_TOKEN))
                recent_job_df = pd.read_csv(fetch_csv_from_github(RECENT_CSV_URL, GITHUB_TOKEN))
                historical_job_df = pd.read_csv(fetch_csv_from_github(HISTORICAL_CSV_URL, GITHUB_TOKEN))
                new_EXT_df = pd.read_csv(fetch_csv_from_github(CURRENT_EXT_URL, GITHUB_TOKEN))
                recent_EXT_df = pd.read_csv(fetch_csv_from_github(RECENT_EXT_URL, GITHUB_TOKEN))
                historical_EXT_df = pd.read_parquet(fetch_parquet_from_github(HISTORICAL_EXT_URL, GITHUB_TOKEN))

                combined_job_df = pd.concat([recent_job_df, new_job_df, historical_job_df])
                combined_job_df = combined_job_df.loc[:, ~combined_job_df.columns.str.contains('^Unnamed')]
                combined_EXT_df = pd.concat([recent_EXT_df, new_EXT_df, historical_EXT_df])
                combined_EXT_df = combined_EXT_df.loc[:, ~combined_EXT_df.columns.str.contains('^Unnamed')]

                combined_df = pd.merge(combined_job_df, combined_EXT_df, on='Job ID', how='left').drop_duplicates(subset='Job ID')
                combined_df['Salary Min'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Min'))
                combined_df['Salary Max'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Max'))
                combined_df['Closing Date Object'] = pd.to_datetime(combined_df['Closing Date'], errors='coerce')
                combined_df['Closing Date'] = combined_df['Closing Date Object'].dt.strftime('%Y-%m-%d')
                combined_df['Job ID'] = combined_df['Job ID'].astype(str).str.replace(",", "")

                # Keep only required columns
                return combined_df[
                    ['Job ID', 'Job Title', 'Job Code', 'Organization', 'Division',
                     'Salary Min', 'Salary Max', 'Location', 'Address',
                     'Closing Date', 'Closing Date Object']
                ]

            # =========================
            # MAIN APP
            # =========================
            st.title("OPS Jobs Data")
            combined_df = load_data()

            with st.sidebar:
                salary_filter = st.slider("Select Salary Range", max_value=200000, value=(MIN_SALARY, MAX_SALARY))
                organizations = combined_df['Organization'].unique()
                organization_filter = st.selectbox("Select Organization", ["All"] + list(organizations))
                location_filter = st.text_input("Location", "").lower()
                start_date, end_date = st.date_input(
                    "Select Date Range",
                    value=(datetime.today(), datetime.today() + timedelta(weeks=4)),
                    min_value=combined_df['Closing Date Object'].min()
                )
                show_EXT_data = st.checkbox('Show EXT Data', value=False)
                show_restricted = st.checkbox('Show TDA Jobs', value=False)
                show_int_URL = st.checkbox('Internal URLs', value=False)
                show_CPI_adjusted_salary = st.checkbox('Show Inflation Adjusted Salaries', value=False)

            # Apply filters
            filtered_df = combined_df[
                (combined_df['Closing Date Object'] >= pd.to_datetime(start_date)) &
                (combined_df['Closing Date Object'] <= pd.to_datetime(end_date)) &
                (combined_df['Salary Min'] >= salary_filter[0]) &
                (combined_df['Salary Max'] <= salary_filter[1]) &
                ((combined_df['Organization'] == organization_filter) | (organization_filter == "All")) &
                (combined_df['Location'].str.lower().str.contains(location_filter))
            ]

            if not show_restricted:
                filtered_df = filtered_df[~filtered_df['Job Title'].str.lower().str.contains('restricted to')]

            filtered_df['Link'] = filtered_df['Job ID'].apply(
                lambda x: f"https://intra.employees.careers.gov.on.ca/Preview.aspx?JobID={x}"
                if show_int_URL else f"https://www.gojobs.gov.on.ca/Preview.aspx?Language=English&JobID={x}"
            )

            if show_CPI_adjusted_salary:
                filtered_df['Closing Year'] = filtered_df['Closing Date Object'].dt.year
                filtered_df['Salary Min'] = filtered_df.apply(lambda x: adjust_salary_with_year(x['Salary Min'], x['Closing Year']), axis=1)
                filtered_df['Salary Max'] = filtered_df.apply(lambda x: adjust_salary_with_year(x['Salary Max'], x['Closing Year']), axis=1)

            # Display table
            display_df = filtered_df.sort_values(by=['Closing Date', 'Salary Min'])
            st.dataframe(display_df, hide_index=True)

            # Plot job count by date
            if display_df.shape[0] > 0:
                col1, col2 = st.columns(2)
                with col1:
                    filtered_df['Date'] = filtered_df['Closing Date Object'].dt.strftime('%Y-%m-%d')
                    fig = px.histogram(filtered_df, x='Date', title="Count of Jobs by Date")
                    st.plotly_chart(fig)
                with col2:
                    salary_data = filtered_df['Salary Min'].dropna()
                    fig = px.histogram(salary_data, x=salary_data, nbins=30, title="Distribution of Salaries")
                    st.plotly_chart(fig)

        else:
            st.error("Invalid authentication code")

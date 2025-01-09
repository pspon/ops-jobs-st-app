import streamlit as st
import pandas as pd
import requests
from io import StringIO
from tqdm import tqdm
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import numpy as np

st.set_page_config(layout="wide")

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

# Function to create link emoji
def create_link(url:str) -> str:
    return f'''<a href="{url}">🔗</a>'''

# Fetch the CSV file
csv_file = fetch_csv_from_github(CURRENT_CSV_URL, GITHUB_TOKEN)
new_job_df = pd.read_csv(csv_file)

# Fetch the CSV file
csv_file_recent = fetch_csv_from_github(RECENT_CSV_URL, GITHUB_TOKEN)
recent_job_df = pd.read_csv(csv_file_recent)

combined_df = pd.concat([recent_job_df,new_job_df])
combined_df = combined_df.loc[:, ~combined_df.columns.str.contains('^Unnamed')].reset_index(drop=True)

# Function to calculate annual salary based on different salary types
def calculate_annual_salary(salary_str,type):
    if type == 'Min':
        if 'Per Year' in salary_str:
            salary_range = salary_str.replace('$', '').replace(',', '').replace(' Per Year', '').split(' - ')
            return (float(salary_range[0]))
        elif 'Per Month' in salary_str:
            salary_range = salary_str.replace('$', '').replace(',', '').replace(' Per Month', '').split(' - ')
            return (float(salary_range[0])) * 12
        elif 'Per Week' in salary_str:
            salary_range = salary_str.replace('$', '').replace(',', '').replace(' Per Week', '').split(' - ')
            return (float(salary_range[0])) * 52
        elif 'Per Hour' in salary_str:
            salary_range = salary_str.replace('$', '').replace(',', '').replace(' Per Hour', '').split(' - ')
            return (float(salary_range[0])) * 36.25 * 52
        else:
            return None
    elif type == 'Max':
        if 'Per Year' in salary_str:
            salary_range = salary_str.replace('$', '').replace(',', '').replace(' Per Year', '').split(' - ')
            return (float(salary_range[1]))
        elif 'Per Month' in salary_str:
            salary_range = salary_str.replace('$', '').replace(',', '').replace(' Per Month', '').split(' - ')
            return (float(salary_range[1])) * 12
        elif 'Per Week' in salary_str:
            salary_range = salary_str.replace('$', '').replace(',', '').replace(' Per Week', '').split(' - ')
            return (float(salary_range[1])) * 52
        elif 'Per Hour' in salary_str:
            salary_range = salary_str.replace('$', '').replace(',', '').replace(' Per Hour', '').split(' - ')
            return (float(salary_range[1])) * 36.25 * 52
        else:
            return None
    else:
        return None

# Calculate annual salary for each row with 'Min' type
combined_df['Salary Min'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Min'))

# Calculate annual salary for each row with 'Max' type
combined_df['Salary Max'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Max'))

# Ensure that the "Closing Date" column is in datetime format for proper handling
combined_df['Closing Date'] = pd.to_datetime(combined_df['Closing Date'], errors='coerce')
combined_df['Closing Date Display'] = combined_df['Closing Date'].dt.strftime('%Y-%m-%d')

# Assuming 'Job ID' is the column name in your DataFrame
combined_df['Job ID'] = combined_df['Job ID'].apply(lambda x: str(x).replace(",", ""))

# Streamlit App Layout
st.title("OPS Jobs Data")

# Filter by Minimum Salary
salary_filter = st.slider("Select Salary Range", min_value=50000, max_value=200000, value=(80000, 160000))

# Filter by Organization
organizations = combined_df['Organization'].unique()
organization_filter = st.selectbox("Select Organization", ["All"] + list(organizations))

# Filter by Location (using fuzzy matching)
locations = combined_df['Location'].unique()
location_filter = st.text_input("Fuzzy Search Location", "").lower()

# Filter by Closing Date (Date Range)
start_date, end_date = st.date_input("Select Date Range", value=(datetime.today(), datetime.today() + timedelta(days=15)))

# Apply filters based on Salary Type, Minimum Salary, Organization, Location, and Date Range
filtered_df = combined_df[
    (combined_df['Closing Date'] >= pd.to_datetime(start_date)) &
    (combined_df['Closing Date'] <= pd.to_datetime(end_date)) &
    (combined_df['Salary Min'] >= salary_filter[0]) &
    (combined_df['Salary Max'] <= salary_filter[1]) &
    ((combined_df['Organization'] == organization_filter) | (organization_filter == "All")) &
    (combined_df['Location'].str.lower().str.contains(location_filter))
]



# Add clickable links to Job ID column
filtered_df['Link']  = filtered_df['Job ID'].apply(lambda x: f"https://www.gojobs.gov.on.ca/employees/Preview.aspx?JobID={x}")
#filtered_df['Link'] = [create_link(url) for url in filtered_df["Link"]]

#Order and filter combined_df
column_order = [
    'Job ID',
    'Job Title',
    'Organization',
    'Salary Min',
    'Salary Max',
    'Location',
    'Closing Date',
    'Link',
]
filtered_df = filtered_df[column_order]
filtered_df = filtered_df.sort_values(by=['Closing Date','Salary Min'],ascending=[True,True])




st.data_editor(
    filtered_df,
    column_config={
        "Link": st.column_config.LinkColumn(
            "URL", display_text="Open"
        ),
        "Salary Min": st.column_config.NumberColumn(
            "Salary Min",
            format="$%d",
        ),
        "Salary Max": st.column_config.NumberColumn(
            "Salary Max",
            format="$%d",
        )
    },
    hide_index=True,
)

col1, col2 = st.columns(2)
with col1:
    # Plot 1: Count of Unique Jobs by Closing Date
    st.subheader("Count of Jobs by Closing Date")
    closing_date_counts = filtered_df['Closing Date'].dropna().dt.date.value_counts().sort_index()
    plt.figure(figsize=(10, 6))
    closing_date_counts.plot(kind='bar', color='skyblue')
    plt.title("Count of Unique Jobs by Closing Date")
    plt.xlabel("Closing Date")
    plt.ylabel("Number of Jobs")
    st.pyplot(plt)

with col2:
    # Plot 2: Distribution of Annual Salaries Across Jobs
    st.subheader("Distribution of Annual Salaries Across Jobs")
    plt.figure(figsize=(10, 6))
    sns.histplot(filtered_df['Salary Min'].dropna(), kde=True, color='green', bins=30)
    plt.title("Distribution of Annual Salaries")
    plt.xlabel("Annual Salary")
    plt.ylabel("Frequency")
    st.pyplot(plt)

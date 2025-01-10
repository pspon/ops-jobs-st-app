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
HISTORICAL_CSV_URL = st.secrets["HISTORICAL_CSV_URL"]

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

# Fetch the recent CSV file
csv_file_recent = fetch_csv_from_github(RECENT_CSV_URL, GITHUB_TOKEN)
recent_job_df = pd.read_csv(csv_file_recent)

# Fetch the historical CSV file
csv_file_historical = fetch_csv_from_github(HISTORICAL_CSV_URL, GITHUB_TOKEN)
historical_job_df = pd.read_csv(csv_file_historical)

combined_df = pd.concat([recent_job_df,new_job_df,historical_job_df])
combined_df = combined_df.loc[:, ~combined_df.columns.str.contains('^Unnamed')].reset_index(drop=True)


# Function to calculate annual salary based on different salary types
def calculate_annual_salary(salary_str,type):
    if type == 'Min':
        try:
            salary_str = salary_str.replace(' (MplusM)','')
            salary_range = salary_str.replace('$', '').replace(',', '').split(' Per')[0].split(' - ')
            if 'Per Year'.lower() in salary_str.lower():
                return (float(salary_range[0]))
            elif 'Per Annum'.lower() in salary_str.lower():
                return (float(salary_range[0]))
            elif 'Per Month'.lower() in salary_str.lower():
                return (float(salary_range[0])) * 12
            elif 'Per Week'.lower() in salary_str.lower():
                return (float(salary_range[0])) * 52
            elif 'Per Hour'.lower() in salary_str.lower():
                return (float(salary_range[0])) * 36.25 * 52
        except:
            #print(salary_str)
            return None
    elif type == 'Max':
        try:
            salary_str = salary_str.replace(' (MplusM)','')
            salary_range = salary_str.replace('$', '').replace(',', '').split(' Per')[0].split(' - ')
            if 'Per Year'.lower() in salary_str.lower():
                return (float(salary_range[1]))
            elif 'Per Annum'.lower() in salary_str.lower():
                return (float(salary_range[1]))
            elif 'Per Month'.lower() in salary_str.lower():
                return (float(salary_range[1])) * 12
            elif 'Per Week'.lower() in salary_str.lower():
                return (float(salary_range[1])) * 52
            elif 'Per Hour'.lower() in salary_str.lower():
                return (float(salary_range[1])) * 36.25 * 52
        except:
            #print(salary_str)
            return None
    else:
        return None

# Calculate annual salary for each row with 'Min' type
combined_df['Salary Min'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Min'))

# Calculate annual salary for each row with 'Max' type
combined_df['Salary Max'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Max'))

# Ensure that the "Closing Date" column is in datetime format for proper handling
combined_df['Closing Date Object'] = pd.to_datetime(combined_df['Closing Date'], errors='coerce')
combined_df['Closing Date'] = combined_df['Closing Date Object'].dt.strftime('%Y-%m-%d')

# Assuming 'Job ID' is the column name in your DataFrame
combined_df['Job ID'] = combined_df['Job ID'].apply(lambda x: str(x).replace(",", ""))

# Streamlit App Layout
st.title("OPS Jobs Data")

with st.sidebar:
    # Toggle TDA / restricted posting switch
    show_restricted = st.checkbox('Show Restricted Job Titles', value=False)
    
    # Filter by Minimum Salary
    salary_filter = st.slider("Select Salary Range", max_value=200000, value=(80000, 160000))
    
    # Filter by Organization
    organizations = combined_df['Organization'].unique()
    organization_filter = st.selectbox("Select Organization", ["All"] + list(organizations))
    
    # Filter by Location (using fuzzy matching)
    location_filter = st.text_input("Location", "").lower()
    
    # Filter by Job Title (using fuzzy matching)
    job_filter = st.text_input("Job Title", "").lower()
    
    # Filter by Closing Date (Date Range)
    start_date, end_date = st.date_input("Select Date Range", value=(datetime.today(), datetime.today() + timedelta(weeks=4)), min_value=combined_df['Closing Date Object'].min())



# Apply filters based on Salary Type, Minimum Salary, Organization, Location, and Date Range
filtered_df = combined_df[
    (combined_df['Closing Date Object'] >= pd.to_datetime(start_date)) &
    (combined_df['Closing Date Object'] <= pd.to_datetime(end_date)) &
    (combined_df['Salary Min'] >= salary_filter[0]) &
    (combined_df['Salary Max'] <= salary_filter[1]) &
    ((combined_df['Organization'] == organization_filter) | (organization_filter == "All")) &
    (combined_df['Location'].str.lower().str.contains(location_filter)) &
    (combined_df['Job Title'].str.lower().str.contains(job_filter))
]

# Filter DataFrame based on toggle switch
if show_restricted:
    combined_df = combined_df[combined_df['Job Title'].str.lower().str.contains('restricted to')]
else:
    combined_df = combined_df[~combined_df['Job Title'].str.lower().str.contains('restricted to')]

with st.sidebar:
    # Filter by Job ID
    job_ids = filtered_df['Job ID'].unique()
    job_id_filter = st.multiselect("Job ID", job_ids, default = job_ids)

filtered_df = filtered_df[(filtered_df['Job ID'].isin(job_id_filter))]

# Add clickable links to Job ID column
filtered_df['Link']  = filtered_df['Job ID'].apply(lambda x: f"https://www.gojobs.gov.on.ca/Preview.aspx?Language=English&JobID={x}")
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
display_df = filtered_df[column_order]
display_df = display_df.sort_values(by=['Closing Date','Salary Min'],ascending=[True,True])




st.dataframe(
    display_df,
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
    closing_date_counts = filtered_df['Closing Date Object'].dropna().dt.date.value_counts().sort_index()
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

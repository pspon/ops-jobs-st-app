import streamlit as st
import pandas as pd
import requests
from io import StringIO
from tqdm import tqdm
from datetime import datetime

st.set_page_config(layout="wide")

# Replace with your GitHub personal access token
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]

# GitHub repository details
REPO_OWNER = st.secrets["REPO_OWNER"]
REPO_NAME = st.secrets["REPO_NAME"]
BRANCH = st.secrets["BRANCH"]
DIRECTORY = st.secrets["DIRECTORY"]


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

# URL of the CSV file in the private repo
CURRENT_CSV_URL = st.secrets["CURRENT_CSV_URL"]
RECENT_CSV_URL = st.secrets["RECENT_CSV_URL"]

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

# Function to convert date string to 'YYYY-MM-DD' format
def convert_date_format(date_str):
    # Remove the time part from the date string
    date_str = ' '.join(date_str.split()[:4])
    # Parse the date string and convert to desired format
    date_obj = datetime.strptime(date_str, "%A, %B %d, %Y")
    return date_obj.strftime("%Y-%m-%d")

# Function to convert date string to 'YYYY-MM-DD' format
def convert_date_format_filter(date_str):
    # Remove the time part from the date string
    date_str = ' '.join(date_str.split()[:4])
    # Parse the date string and convert to desired format
    date_obj = datetime.strptime(date_str, "%A, %B %d, %Y")
    return date_obj

# Filter for closing date today or later
# Apply the function to the 'Closing Date' column
combined_df['Closing Date Obj'] = combined_df['Closing Date'].apply(convert_date_format_filter)
combined_df = combined_df[combined_df['Closing Date Obj'] >= datetime.today()]

# Apply the function to the 'Closing Date' column
combined_df['Closing Date'] = combined_df['Closing Date'].apply(convert_date_format)

# Assuming 'Job ID' is the column name in your DataFrame
combined_df['Job ID'] = combined_df['Job ID'].apply(lambda x: str(x).replace(",", ""))

st.write(combined_df.shape)

#Order and filter combined_df
column_order = [
    'Job ID',
    'Job Title',
    'Organization',
    'Salary Min',
    'Salary Max',
    'Location',
    'Closing Date',
]
combined_df = combined_df[column_order]
combined_df = combined_df.sort_values(by="CLosing Date",ascending=True)

# Display the DataFrame in Streamlit
st.write(combined_df)


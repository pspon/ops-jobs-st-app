import streamlit as st
import pandas as pd
import requests
from io import StringIO, BytesIO
from tqdm import tqdm
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
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
    
# Function to create link emoji
def create_link(url:str) -> str:
    return f'''<a href="{url}">🔗</a>'''

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

def adjust_salary_with_year(salary, salary_year):
    """
    Adjusts a salary based on the year it was set, using updated CPI values for Canada (2008-2024).
    
    Parameters:
    - salary (float): The initial salary to be adjusted.
    - salary_year (int): The year the salary was set.

    Returns:
    - float: The adjusted salary for the most recent year.
    """
    # Updated CPI values for Canada (2008-2024, average annual CPI)
    cpi_data = {
        2008: 114.1, 2009: 114.4, 2010: 116.5, 2011: 119.9, 2012: 121.7,
        2013: 122.8, 2014: 125.2, 2015: 126.6, 2016: 128.4, 2017: 130.4,
        2018: 133.4, 2019: 136.0, 2020: 137.0, 2021: 141.6, 2022: 151.2,
        2023: 157.1, 2024: 160.6  # CPI 2024 not final, average of 12 months from Dec 2023 to Nov 2024
    }

    salary_year = int(salary_year)
    salary = float(salary)
    
    # Ensure the year is valid, if not, return original salary
    if salary_year not in cpi_data:
        #raise ValueError(f"Salary year must be between {min(cpi_data.keys())} and {max(cpi_data.keys())}.")
        return salary
        
    # Return original salary if salary year is current year, no adjustment needed
    current_year = datetime.now().year
    if salary_year == current_year:
        return salary
        
    # Get the base and current CPI
    base_cpi = cpi_data[salary_year]
    current_cpi = cpi_data[max(cpi_data.keys())]  # Most recent year
    
    # Adjust salary based on the CPI ratio
    adjusted_salary = salary * (current_cpi / base_cpi)
    return round(adjusted_salary, 2)

# Function to apply the boolean filter logic to the DataFrame
def apply_filter(df, conditions):
    # Start with the first condition
    condition = conditions[0]['filter']
    
    for i in range(1, len(conditions)):
        if conditions[i]['logic'] == 'AND':
            condition &= conditions[i]['filter']
        elif conditions[i]['logic'] == 'OR':
            condition |= conditions[i]['filter']
        elif conditions[i]['logic'] == 'NOT':
            condition &= ~conditions[i]['filter']
    
    # Apply the final condition to filter the DataFrame
    return df[condition]

@st.cache_data
def load_data(ttl=3600):
    # Fetch the current CSV file
    csv_file = fetch_csv_from_github(CURRENT_CSV_URL, GITHUB_TOKEN)
    new_job_df = pd.read_csv(csv_file)

    # Fetch the recent CSV file
    csv_file_recent = fetch_csv_from_github(RECENT_CSV_URL, GITHUB_TOKEN)
    recent_job_df = pd.read_csv(csv_file_recent)

    # Fetch the historical CSV file
    csv_file_historical = fetch_csv_from_github(HISTORICAL_CSV_URL, GITHUB_TOKEN)
    historical_job_df = pd.read_csv(csv_file_historical)

    # Fetch the current EXT file
    EXT_file = fetch_csv_from_github(CURRENT_EXT_URL, GITHUB_TOKEN)
    new_EXT_df = pd.read_csv(EXT_file)

    # Fetch the recent EXT file
    EXT_file_recent = fetch_csv_from_github(RECENT_EXT_URL, GITHUB_TOKEN)
    recent_EXT_df = pd.read_csv(EXT_file_recent)

    # Fetch the historical EXT file
    EXT_file_historical = fetch_parquet_from_github(HISTORICAL_EXT_URL, GITHUB_TOKEN)
    historical_EXT_df = pd.read_parquet(EXT_file_historical)

    # Join dfs
    combined_job_df = pd.concat([recent_job_df,new_job_df,historical_job_df])
    combined_job_df = combined_job_df.loc[:, ~combined_job_df.columns.str.contains('^Unnamed')].reset_index(drop=True)
    combined_EXT_df = pd.concat([recent_EXT_df,new_EXT_df,historical_EXT_df])
    combined_EXT_df = combined_EXT_df.loc[:, ~combined_EXT_df.columns.str.contains('^Unnamed')].reset_index(drop=True)
    combined_df = pd.merge(combined_job_df, combined_EXT_df, on='Job ID', how='left').drop_duplicates(subset='Job ID')
    combined_df = combined_df.loc[:, ~combined_df.columns.str.contains('^Unnamed')].reset_index(drop=True)

    # Calculate annual salary for each row with 'Min' type
    combined_df['Salary Min'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Min'))

    # Calculate annual salary for each row with 'Max' type
    combined_df['Salary Max'] = combined_df['Salary'].apply(lambda x: calculate_annual_salary(x, 'Max'))

    # Assuming 'combined_df' is your DataFrame and 'Closing Date' is the column with date strings
    combined_df['Closing Date'] = combined_df['Closing Date'].str.replace(' EST', '').str.replace(' EDT', '')  # Remove both timezone parts
    combined_df['Closing Date Object'] = pd.to_datetime(combined_df['Closing Date'], errors='coerce')
    combined_df['Closing Date Object'] = combined_df['Closing Date Object'].dt.tz_localize('America/New_York', ambiguous='NaT')  # Add the correct timezone
    combined_df['Closing Date'] = combined_df['Closing Date Object'].dt.strftime('%Y-%m-%d')

    # Assuming 'Job ID' is the column name in your DataFrame
    combined_df['Job ID'] = combined_df['Job ID'].apply(lambda x: str(x).replace(",", ""))
    return(combined_df)

# Load data with cache
combined_df = load_data()

# Streamlit App Layout
st.title("OPS Jobs Data")

#st.dataframe(combined_df[combined_df['Job ID'] == '226674'])


# List to hold the user-defined filter conditions
conditions = []

with st.sidebar:
    # Filter by Minimum Salary
    salary_filter = st.slider("Select Salary Range", max_value=200000, value=(MIN_SALARY, MAX_SALARY))
    
    # Filter by Organization
    organizations = combined_df['Organization'].unique()
    organization_filter = st.selectbox("Select Organization", ["All"] + list(organizations))
    #organization_filter = st.container(height=70).multiselect("Select Organizations", options=organizations, default=organizations)

    # Filter by Location (using fuzzy matching)
    location_filter = st.text_input("Location", "").lower()


    # Loop to allow dynamic addition of filters
    num_filters = st.number_input("Number of Job Title Filters", min_value=1, max_value=5, value=1, step=1)
    
    for i in range(num_filters):
        
        # Logic operator dropdown for filters after the first one
        if i > 0:
            logic_operator = st.selectbox(
                f"Logical Operator for Filter {i+1}",
                ('AND', 'OR', 'NOT'),
                key=f"operator_{i+1}"
            )
        else:
            # The first filter does not require an operator, so we default to 'AND'
            logic_operator = 'AND'
        
        # Text entry for the filter condition
        filter_text = st.text_input(f"Filter {i+1}", "")
        
        # Construct the condition based on user input
        if filter_text:
            filter_condition = combined_df['Job Title'].str.lower().str.contains(filter_text.lower(), case=False, na=False)
            conditions.append({'filter': filter_condition, 'logic': logic_operator})
    
    # Filter by Job Title (using fuzzy matching)
    #job_filter = st.text_input("Job Title", "").lower()
    
    # Filter by Closing Date (Date Range)
    start_date, end_date = st.date_input("Select Date Range", value=(datetime.today(), datetime.today() + timedelta(weeks=4)), min_value=combined_df['Closing Date Object'].min())

    # Toggle EXT info switch
    show_EXT_data = st.checkbox('Show EXT Data', value=False)
    if show_EXT_data == True:
        # Filter by Division
        division_filter = st.text_input("Division", "").lower()
        # Filter by Address (using fuzzy matching)
        address_filter = st.text_input("Address", "").lower()

    # Toggle TDA / restricted posting switch
    show_restricted = st.checkbox('Show TDA Jobs', value=False)

    # Toggle job url templates
    show_int_URL = st.checkbox('Internal URLs', value=False)

    # Toggle inflation adjusted salary
    show_CPI_adjusted_salary = st.checkbox('Show Inflation Adjusted Salaries', value=False)

if show_EXT_data == False:
    # Apply filters based on Salary Type, Minimum Salary, Organization, Location, and Date Range
    filtered_df = combined_df[
        (combined_df['Closing Date Object'] >= pd.to_datetime(start_date)).dt.tz_localize('America/New_York', ambiguous='NaT') &
        (combined_df['Closing Date Object'] <= pd.to_datetime(end_date)).dt.tz_localize('America/New_York', ambiguous='NaT') &
        (combined_df['Salary Min'] >= salary_filter[0]) &
        (combined_df['Salary Max'] <= salary_filter[1]) &
        ((combined_df['Organization'] == organization_filter) | (organization_filter == "All")) &
        (combined_df['Location'].str.lower().str.contains(location_filter))
        #(combined_df['Organization'].isin(organization_filter)) &
        #(combined_df['Job Title'].str.lower().str.contains(job_filter))
    ]
elif show_EXT_data == True:
    # Apply filters based on Salary Type, Minimum Salary, Organization, Location, and Date Range INCLUDING EXT fields
    filtered_df = combined_df[
        (combined_df['Closing Date Object'] >= pd.to_datetime(start_date)).dt.tz_localize('America/New_York', ambiguous='NaT') &
        (combined_df['Closing Date Object'] <= pd.to_datetime(end_date)).dt.tz_localize('America/New_York', ambiguous='NaT') &
        (combined_df['Salary Min'] >= salary_filter[0]) &
        (combined_df['Salary Max'] <= salary_filter[1]) &
        ((combined_df['Organization'] == organization_filter) | (organization_filter == "All")) &
        (combined_df['Location'].str.lower().str.contains(location_filter)) &
        #(combined_df['Organization'].isin(organization_filter)) &
        #(combined_df['Job Title'].str.lower().str.contains(job_filter))
        (combined_df['Division'].str.lower().str.contains(division_filter)) &
        (combined_df['Address'].str.lower().str.contains(address_filter)) #&
    ]    
#st.dataframe(filtered_df[filtered_df['Job ID'] == '226674'])
# Display the resulting filtered DataFrame
if len(conditions) > 0:
    filtered_df = apply_filter(filtered_df, conditions)
else:
    st.write("No filters applied.")
    
# Filter DataFrame based on toggle switch
if show_restricted:
    filtered_df = filtered_df[filtered_df['Job Title'].str.lower().str.contains('restricted to')]
else:
    filtered_df = filtered_df[~filtered_df['Job Title'].str.lower().str.contains('restricted to')]

# Add clickable links to Job ID column
if show_int_URL == True:
    filtered_df['Link']  = filtered_df['Job ID'].apply(lambda x: f"https://intra.employees.careers.gov.on.ca/Preview.aspx?JobID={x}")
else:
    filtered_df['Link']  = filtered_df['Job ID'].apply(lambda x: f"https://www.gojobs.gov.on.ca/Preview.aspx?Language=English&JobID={x}")
#filtered_df['Link'] = [create_link(url) for url in filtered_df["Link"]]

# Inflation-adjusted salary toggle
if show_CPI_adjusted_salary == True:
    # Extract the year from the "Closing Date Object"
    filtered_df['Closing Year'] = filtered_df['Closing Date Object'].dt.year
    
    # Adjust the 'Salary Min' and 'Salary Max' based on the year from 'Closing Year'
    filtered_df['Salary Min'] = filtered_df.apply(lambda x: adjust_salary_with_year(x['Salary Min'], x['Closing Year']), axis=1)
    filtered_df['Salary Max'] = filtered_df.apply(lambda x: adjust_salary_with_year(x['Salary Max'], x['Closing Year']), axis=1)

with st.sidebar:
    # Filter by Job ID
    job_ids = filtered_df['Job ID'].unique()
    job_id_filter = st.multiselect("Job ID", job_ids, default = job_ids)

filtered_df = filtered_df[(filtered_df['Job ID'].isin(job_id_filter))]


if show_EXT_data == False:
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
elif show_EXT_data == True:
    #Order and filter combined_df
    column_order = [
        'Job ID',
        'Job Title',
        'Organization',
        'Division',
        'Salary Min',
        'Salary Max',
        'Location',
        'Address',
        'Closing Date',
        'Link',
    ]
display_df = filtered_df[column_order]
display_df = display_df.sort_values(by=['Closing Date','Salary Min'],ascending=[True,True])

if display_df.shape[0] > 0:
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
        # Plot 1: Count of Jobs by Closing Date (Binned by Date in YYYY-MM-DD format)
        st.subheader("Count of Jobs by Date of Closing Date")
        
        # Ensure 'Closing Date Object' is datetime
        filtered_df['Closing Date Object'] = pd.to_datetime(filtered_df['Closing Date Object'], errors='coerce')
        
        # Create a new column with Date in YYYY-MM-DD format
        filtered_df['Date'] = filtered_df['Closing Date Object'].dt.strftime('%Y-%m-%d')

        # Create the plot with Plotly
        fig = px.histogram(
            filtered_df,
            x='Date',
            labels={'Date': 'Date', 'count': 'Number of Jobs'},
            title="Count of Jobs by Date of Closing Date",
            histfunc='count',  # This tells Plotly to count occurrences
            template='plotly'
        )
        
        # Update the x-axis to display in YYYY-MM-DD format
        fig.update_xaxes(
            tickformat="%Y-%m-%d",  # Show Date in YYYY-MM-DD format
            title="Date"
        )

        fig.update_yaxes(
            title="Number of Jobs"
        )
        
        # Display the plot
        st.plotly_chart(fig)
    
    with col2:
        # Plot 2: Interactive Distribution of Annual Salaries Across Jobs
        st.subheader("Distribution of Annual Salaries Across Jobs")
        
        # Drop NaN values and create an interactive histogram using Plotly
        salary_data = filtered_df['Salary Min'].dropna()
    
        # Create the plot with Plotly
        fig = px.histogram(
            salary_data,
            x=salary_data,
            nbins=30,  # Number of bins for the histogram
            labels={'x': 'Annual Salary', 'count': 'Frequency'},
            title="Distribution of Annual Salaries Across Jobs",
            template='plotly',
        )
        
        # Update the layout to make the plot more readable
        fig.update_layout(
            xaxis_title="Annual Salary",
            yaxis_title="Frequency",
            bargap=0.2,  # Gap between bars
            hovermode="x unified",  # Unified hover label on the x-axis
        )
        
        # Display the Plotly chart in Streamlit
        st.plotly_chart(fig)
else:
    st.write('No jobs available')

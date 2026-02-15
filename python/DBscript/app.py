import mysql.connector
import os
import pandas as pd
import time
from dotenv import load_dotenv
import streamlit as st

# Set Streamlit layout
st.set_page_config(layout='wide', initial_sidebar_state='expanded')

# Load custom CSS
with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.sidebar.header('Dashboard `version 2`')

# Sidebar inputs (remove if not used)
# time_hist_color = st.sidebar.selectbox('Color by', ('temp_min', 'temp_max'))
# plot_data = st.sidebar.multiselect('Select data', ['temp_min', 'temp_max'], ['temp_min', 'temp_max'])
# plot_height = st.sidebar.slider('Specify plot height', 200, 500, 250)

# Environment variables
load_dotenv()

# Database credentials
DB_HOST = os.getenv("DB_HOST")
DB_HOST2 = os.getenv("DB_HOST2")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Constants
MAX_CONNECTION_ATTEMPTS = 3
QUERY_TIMEOUT_SECONDS = 2

def create_connection():
    """Create a connection to the MySQL database."""
    hosts = [DB_HOST, DB_HOST2]
    for host in hosts:
        for attempt in range(MAX_CONNECTION_ATTEMPTS):
            try:
                connection = mysql.connector.connect(
                    host=host,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    connect_timeout=10
                )
                if connection.is_connected():
                    st.info(f"Connected successfully to {host}.")
                    return connection
            except mysql.connector.Error as err:
                st.error(f"Attempt {attempt + 1} failed for {host}: {err}")
                if attempt == MAX_CONNECTION_ATTEMPTS - 1:
                    st.error(f"Failed to connect to {host} after {MAX_CONNECTION_ATTEMPTS} attempts.")
                time.sleep(QUERY_TIMEOUT_SECONDS)
    return None

def fetch_databases():
    """Fetch all databases from the MySQL server."""
    connection = create_connection()
    if connection is None:
        return []
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        return [database[0] for database in databases]
    except Exception as e:
        st.error(f"Error fetching databases: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        connection.close()

def get_queries(database_name):
    """Return SQL queries for a given database."""
    return {
        "Check Offline Bridges": f"""
            USE {database_name};
            SELECT
                l.locationname,
                l.bookgroup,
                l.branchid,
                l.guilocationdataid,
                b.hostname,
                b.bridgetype,
                b.comment AS bridge_comment,
                b.swversion,
                b.bridgestate,
                l.locationname AS bridge_location
            FROM
                inbridge b
            JOIN
                device d ON b.inbridgeid = d.inbridgeid
            JOIN
                location l ON d.locationid = l.locationid
            WHERE
                b.bridgestate IS NULL OR b.bridgestate != 'OPEN';
        """
    }

def export_for_customer(database_name):
    """Export bridge data for a specific customer database."""
    connection = create_connection()
    if connection is None:
        st.error(f"Failed to create a connection to {database_name}")
        return None

    queries = get_queries(database_name)
    df_dict = {}

    for query_name, query in queries.items():
        cursor = None
        try:
            cursor = connection.cursor()
            for statement in query.split(';'):
                if statement.strip():
                    cursor.execute(statement)
            results = cursor.fetchall()
            if not results:
                st.warning(f"No results for query '{query_name}' in database {database_name}.")
                continue
            if cursor.description is None:
                st.error(f"Cursor description is missing for query '{query_name}' in {database_name}.")
                continue
            column_names = [desc[0] for desc in cursor.description]
            df = pd.DataFrame(results, columns=column_names)
            df_dict[query_name] = df
        except mysql.connector.Error as e:
            st.error(f"MySQL error executing query '{query_name}' for {database_name}: {e}")
        except Exception as e:
            st.error(f"Error executing query '{query_name}' for {database_name}: {e}")
        finally:
            if cursor:
                cursor.close()
    connection.close()
    return df_dict if df_dict else None

def find_customers_with_offline_bridges():
    """Find customers with offline or non-OPEN bridges."""
    databases = fetch_databases()
    if not databases:
        st.error("No databases found.")
        return []

    customers_with_issues = []
    with st.spinner("Checking all customer databases..."):
        for database in databases:
            df_dict = export_for_customer(database)
            if df_dict is None:
                st.error(f"No data returned for database: {database}")
                continue
            for query_name, df in df_dict.items():
                if not df.empty:
                    customers_with_issues.append({
                        'customer': database,
                        'bridges_with_issues': df
                    })
    return customers_with_issues

def display_data_on_dashboard():
    """Display the summary table on the Streamlit dashboard."""
    st.title("Customers with Offline or Non-OPEN Bridges")
    customers_with_issues = find_customers_with_offline_bridges()
    if not customers_with_issues:
        st.write("No customers with offline or non-OPEN bridges.")
        return
    table_data = [{'Customer': issue['customer'], 'Issues Found': len(issue['bridges_with_issues'])}
                  for issue in customers_with_issues]
    customer_df = pd.DataFrame(table_data)
    st.dataframe(customer_df, use_container_width=True)
    # Optionally, allow user to expand and see details per customer
    for issue in customers_with_issues:
        with st.expander(f"Details for {issue['customer']}"):
            st.dataframe(issue['bridges_with_issues'], use_container_width=True)

def main():
    display_data_on_dashboard()

if __name__ == "__main__":
    main()

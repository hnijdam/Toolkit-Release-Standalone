from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector
import os
import pandas as pd
import time
import getpass
import re
from concurrent.futures import ThreadPoolExecutor

# Environment variables
load_dotenv()

# Settings
EXCEL_FILE_NAME_FORMAT = "{}_{}.xlsx"
MAX_CONNECTION_ATTEMPTS = 3
QUERY_TIMEOUT_SECONDS = 2
EXPORT_DIRECTORY = r"Y:\Support\Proactief werken"
MAX_COLUMN_WIDTH = 50  # Max width for Excel columns

# Database credentials
DB_HOST = os.getenv("DB_HOST")
DB_HOST2 = os.getenv("DB_HOST2")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Fallback naar terminal input wanneer credentials niet in environment file staan.
if not DB_USER:
    DB_USER = input("Voer de database username in: ")
if not DB_PASSWORD:
    DB_PASSWORD = getpass.getpass("Voer het ICY database wachtwoord in: ")

# Inladen source file
with open(r"Y:\Support\Proactief werken\Script\klanten.txt") as file:
    customers = [customer.strip() for customer in file]

# Queries ophalen
def get_queries(database_name):
    queries = {
        # Aangepaste query voor het ophalen van controllers en slavedevices
        "Devices en slavedevices met comq": f"""
            SELECT
                CONCAT('Controller: ', l.bookgroup, ' ', l.locationname) AS controller_name,
                sd.slavedevicetypeid,
                dt.icyname AS slavedevice_name,
                sd.comcount,
                sd.comquality,
                sd.inbridgeid,  -- inbridgeid van de slavedevice
                b.hostname,     -- hostname van de inbridge
                b.bridgetype,   -- bridgetype van de inbridge
                b.comment,      -- comment van de inbridge
                b.swversion,    -- swversion van de inbridge
                b.bridgestate   -- bridgestate van de inbridge
            FROM
                {database_name}.device d
            JOIN
                {database_name}.slavedevice sd ON d.deviceid = sd.deviceid
            JOIN
                {database_name}.location l ON d.locationid = l.locationid
            JOIN
                {database_name}.devicetype dt ON sd.slavedevicetypeid = dt.devicetypeid
            LEFT JOIN
                {database_name}.inbridge b ON sd.inbridgeid = b.inbridgeid  -- Left join voor de inbridge tabel
            WHERE
                d.devicetypeid IN (56, 57, 59, 60)  -- Alleen controllers
        """,

        # Query om locatiegegevens van de controllers op te halen, inclusief inbridge-informatie
        "Controller locaties": f"""
            SELECT
                l.locationname,
                l.bookgroup,
                l.branchid,
                l.guilocationdataid,
                b.hostname,     -- hostname van de inbridge
                b.bridgetype,   -- bridgetype van de inbridge
                b.comment,      -- comment van de inbridge
                b.swversion,    -- swversion van de inbridge
                b.bridgestate   -- bridgestate van de inbridge
            FROM
                {database_name}.device d
            JOIN
                {database_name}.location l ON d.locationid = l.locationid
            LEFT JOIN
                {database_name}.inbridge b ON d.inbridgeid = b.inbridgeid  -- Left join voor de inbridge tabel
            WHERE
                d.devicetypeid IN (56, 57, 59, 60)  -- Alleen controllers
        """,

        # Query om details van de devices op te halen, inclusief inbridge-informatie
        "Devices per typeid en aantal": f"""
            SELECT
                dt.devicetypeid,
                COUNT(d.deviceid) AS device_count,
                b.hostname,     -- hostname van de inbridge
                b.bridgetype,   -- bridgetype van de inbridge
                b.comment,      -- comment van de inbridge
                b.swversion,    -- swversion van de inbridge
                b.bridgestate   -- bridgestate van de inbridge
            FROM
                {database_name}.device d
            JOIN
                {database_name}.devicetype dt ON d.devicetypeid = dt.devicetypeid
            LEFT JOIN
                {database_name}.inbridge b ON d.inbridgeid = b.inbridgeid  -- Left join voor de inbridge tabel
            GROUP BY
                dt.devicetypeid, b.hostname, b.bridgetype, b.comment, b.swversion, b.bridgestate
        """,

        # Query om offline devices per devicetypeid te verkrijgen, inclusief inbridge-informatie
        "Offline devices by devicetypeid": f"""
            SELECT
                dt.devicetypeid,
                d.deviceid,
                d.devid,
                d.address,
                b.hostname,     -- hostname van de inbridge
                b.bridgetype,   -- bridgetype van de inbridge
                b.comment,      -- comment van de inbridge
                b.swversion,    -- swversion van de inbridge
                b.bridgestate   -- bridgestate van de inbridge
            FROM
                {database_name}.device d
            JOIN
                {database_name}.devicetype dt ON d.devicetypeid = dt.devicetypeid
            LEFT JOIN
                {database_name}.inbridge b ON d.inbridgeid = b.inbridgeid  -- Left join voor de inbridge tabel
            WHERE
                d.devicetypeid NOT IN (56, 57, 59, 60)  -- Andere devices dan controllers
            GROUP BY
                dt.devicetypeid, d.deviceid, d.devid, d.address, b.hostname, b.bridgetype, b.comment, b.swversion, b.bridgestate
        """,

        # Query voor de inbridge tabel
        "Inbridge data": f"""
            SELECT
                hostname,
                bridgetype,
                comment,
                swversion,
                bridgestate
            FROM
                {database_name}.inbridge
            GROUP BY
                hostname, bridgetype, comment, swversion, bridgestate;
        """
    }
    return queries

# Maak een database verbinding met fallback naar de secondary host
def create_connection(database_name):
    hosts = [DB_HOST, DB_HOST2]
    for host in hosts:
        for attempt in range(MAX_CONNECTION_ATTEMPTS):
            try:
                print(f"Trying to connect to {host} (Attempt {attempt + 1})")
                connection = mysql.connector.connect(
                    host=host,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=database_name,
                    connect_timeout=10  # Timeout added here
                )
                if connection.is_connected():
                    print(f"Connection successful to {host}!")
                    return connection
            except mysql.connector.Error as err:
                if err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
                    print(f"Database '{database_name}' does not exist on {host}.")
                    break
                elif err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
                    print("Authentication failed, please check your credentials.")
                elif err.errno == mysql.connector.errorcode.ER_DBACCESS_DENIED_ERROR:
                    print(f"Access to database '{database_name}' denied.")
                elif err.errno == mysql.connector.errorcode.CR_SERVER_LOST:
                    print(f"Lost connection to {host}, retrying...")
                else:
                    print(f"Connection attempt {attempt + 1} to {host} failed: {err}")
                    time.sleep(QUERY_TIMEOUT_SECONDS)
        print(f"Failed to connect to {host}. Trying the next host if available.")
    print("Failed to connect after multiple attempts to all hosts.")
    return None

# Exporteer gegevens voor een specifieke klant
def export_for_customer(database_name):
    connection = create_connection(database_name)
    if connection is None:
        print(f"Skipping customer {database_name} due to connection issues.")
        return

    queries = get_queries(database_name)
    df_dict = {}

    for query_name, query in queries.items():
        try:
            df = pd.read_sql(query, connection)
            df_dict[query_name] = df
            print(f"Executed query: {query_name} for {database_name}")
        except Exception as e:
            print(f"Error executing query '{query_name}' for {database_name}: {e}")
            continue

    connection.close()

    if df_dict:
        today = datetime.now().strftime("%Y-%m-%d")
        file_name = EXCEL_FILE_NAME_FORMAT.format(database_name, today)
        export_to_excel(df_dict, EXPORT_DIRECTORY, file_name)
    else:
        print(f"No data retrieved for {database_name}, skipping Excel export.")

# Exporteer query resultaten naar een Excel-bestand met controllers en slavedevices gegroepeerd en een lege regel ertussen
def export_to_excel(df_dict, directory_name, file_name):
    excel_file_path = os.path.join(directory_name, file_name)

    with pd.ExcelWriter(excel_file_path, engine="openpyxl") as writer:
        for sheet_name, df in df_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            for col_num, col in enumerate(df.columns, 1):
                max_length = max(df[col].astype(str).apply(len).max(), len(col))
                adjusted_width = min(max_length, MAX_COLUMN_WIDTH)
                worksheet.column_dimensions[get_column_letter(col_num)].width = adjusted_width

            table = Table(displayName=sheet_name, ref=worksheet.dimensions)
            worksheet.add_table(table)
            table_style = TableStyleInfo(name="TableStyleMedium9", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=True)
            table.tableStyleInfo = table_style

    print(f"Export complete: {excel_file_path}")

# Parallelle uitvoering van klantexport
def main():
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(export_for_customer, customers)

if __name__ == "__main__":
    main()

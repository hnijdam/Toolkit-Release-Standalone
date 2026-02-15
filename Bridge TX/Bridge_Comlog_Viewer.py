import argparse
import csv
import getpass
import mysql.connector
import os
import pandas as pd
import sys
from visualize2 import visualize_bridge_csv_comlog





def _clean_arg(value):
    return value.strip().strip(",")


def _get_output_dir():
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        output_dir = os.path.join(user_profile, "Documents", "ICY-Logs")
    else:
        output_dir = "C:/tmp"
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def comlog_overzicht_bridge(
    database,
    klant_db_naam,
    aantal_min_geleden,
    db_gebruiker,
    db_password,
    filter_input,
    sort_by="bridge_id",
):
    try:
        database = _clean_arg(database).lower()
        klant_db_naam = _clean_arg(klant_db_naam)
        aantal_min_geleden = int(_clean_arg(str(aantal_min_geleden)))
        db_gebruiker = _clean_arg(db_gebruiker)
        db_password = _clean_arg(db_password)
        filter_input = _clean_arg(filter_input)
        sort_by = _clean_arg(sort_by)

        if database == "mariadb":
            host = "icyccdb02.icy.nl"
            #db_password = mariadb_pwd

        elif database == "mysql":
            host = 'icyccdb.icy.nl'
            print("test")
            #db_password = mysql_pwd
        else:
            raise ValueError(f"Unsupported database: {database}")
        conn = mysql.connector.connect(host=host, user=db_gebruiker, password=db_password, port=3306, use_pure=True)
        cursor = conn.cursor()

        #if no filter input then use standard filter on bridge communication = ab abab
        if len(filter_input) == 0:
            filter_input = "ab abab"

        output_dir = _get_output_dir()

        # Get Filtered data
        cursor.execute(
            f'SELECT c.*, b.bridgetype, b.swversion, b.polling, b.pollfailure FROM {klant_db_naam}.communicationlog AS c LEFT JOIN {klant_db_naam}.inbridge AS b ON c.inbridgeid = b.inbridgeid WHERE c.direction = 1 AND c.timestamp >= NOW() - INTERVAL {aantal_min_geleden} MINUTE AND c.comment LIKE "%{filter_input}%" ORDER BY c.communicationlogid DESC;'
        )
        rows = cursor.fetchall()
        csv_filtered_path = os.path.join(
            output_dir,
            f"bridge_com_overzicht_{klant_db_naam}_{aantal_min_geleden}_min_filtered.csv",
        )
        csv_bestand_filtered = open(csv_filtered_path, 'w', newline='')
        mijn_bestand = csv.writer(csv_bestand_filtered)
        mijn_bestand.writerows(rows)
        csv_bestand_filtered.close()
        print("filetered csv opgeslagen")


        # Get unfiltered data
        cursor.execute(
            f'SELECT c.*, b.bridgetype, b.swversion, b.polling, b.pollfailure FROM {klant_db_naam}.communicationlog AS c LEFT JOIN {klant_db_naam}.inbridge AS b ON c.inbridgeid = b.inbridgeid WHERE c.direction = 1 AND c.timestamp >= NOW() - INTERVAL {aantal_min_geleden} MINUTE AND c.comment NOT LIKE "%{filter_input}%" ORDER BY c.communicationlogid DESC;'
        )
        rows = cursor.fetchall()
        csv_unfiltered_path = os.path.join(
            output_dir,
            f"bridge_com_overzicht_{klant_db_naam}_{aantal_min_geleden}_min_unfiltered.csv",
        )
        csv_bestand_unfiltered = open(csv_unfiltered_path, 'w', newline='')
        mijn_bestand = csv.writer(csv_bestand_unfiltered)
        mijn_bestand.writerows(rows)
        csv_bestand_unfiltered.close()
        print("unfiletered csv opgeslagen")


            #visualize_csv_comlog()
        visualize_bridge_csv_comlog(
            csv_filtered_path,
            csv_unfiltered_path,
            sort_by,
            output_dir,
        )

#SELECT c.*, b.bridgetype, b.swversion, b.polling, b.pollfailure FROM nl_rentaroof.communicationlog AS c LEFT JOIN nl_rentaroof.inbridge AS b ON c.inbridgeid = b.inbridgeid WHERE c.direction = 1 AND c.timestamp >= NOW() - INTERVAL 1440 MINUTE AND c.comment NOT LIKE '%ab abab%' ORDER BY c.communicationlogid DESC;

    except Exception as e:
        print("Foutje", e)


def _prompt_text(label, default=None, required=False, secret=False):
    while True:
        if default is not None:
            prompt = f"{label} [{default}]: "
        else:
            prompt = f"{label}: "

        value = getpass.getpass(prompt) if secret else input(prompt)
        if value == "" and default is not None:
            value = default
        if value or not required:
            return value
        print("Waarde is verplicht.")


def _prompt_int(label, default=None):
    while True:
        raw = _prompt_text(label, default=str(default) if default is not None else None)
        try:
            return int(raw)
        except ValueError:
            print("Ongeldig getal, probeer opnieuw.")


def _load_env_credentials():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.normpath(os.path.join(script_dir, "..", "python", "DBscript", ".env"))
    if not os.path.isfile(env_path):
        return None, None

    user = None
    password = None
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "DB_USER":
                    user = value
                elif key == "DB_PASSWORD":
                    password = value
    except OSError:
        return None, None

    return user, password


def _resolve_args():
    parser = argparse.ArgumentParser(
        description="Bridge comlog viewer (CSV export + visualisatie)."
    )
    parser.add_argument("database", nargs="?")
    parser.add_argument("klant_db_naam", nargs="?")
    parser.add_argument("aantal_min_geleden", nargs="?")
    parser.add_argument("db_gebruiker", nargs="?")
    parser.add_argument("db_password", nargs="?")
    parser.add_argument("filter_input", nargs="?")
    parser.add_argument("sort_by", nargs="?")
    args = parser.parse_args()

    database = args.database
    klant_db_naam = args.klant_db_naam
    aantal_min_geleden = args.aantal_min_geleden
    db_gebruiker = args.db_gebruiker
    db_password = args.db_password
    filter_input = args.filter_input
    sort_by = args.sort_by

    if database is None:
        database = _prompt_text("Database (mysql/mariadb)", required=True).lower()
    if klant_db_naam is None:
        klant_db_naam = _prompt_text("Klant DB naam", required=True)
    if aantal_min_geleden is None:
        aantal_min_geleden = _prompt_int("Aantal minuten terug", default=1440)
    if db_gebruiker is None or db_password is None:
        env_user, env_password = _load_env_credentials()
        if db_gebruiker is None:
            db_gebruiker = env_user
        if db_password is None:
            db_password = env_password

    if db_gebruiker is None:
        db_gebruiker = _prompt_text("DB gebruiker", required=True)
    if db_password is None:
        db_password = _prompt_text("DB password", required=True, secret=True)
    if filter_input is None:
        filter_input = _prompt_text("Filter", default="ab abab")
    if sort_by is None:
        sort_by = _prompt_text("Sorteren op", default="bridge_id")

    return (
        database,
        klant_db_naam,
        aantal_min_geleden,
        db_gebruiker,
        db_password,
        filter_input,
        sort_by,
    )

if __name__ == "__main__":
    (
        database,
        klant_db_naam,
        aantal_min_geleden,
        db_gebruiker,
        db_password,
        filter_input,
        sort_by,
    ) = _resolve_args()

    comlog_overzicht_bridge(
        database,
        klant_db_naam,
        aantal_min_geleden,
        db_gebruiker,
        db_password,
        filter_input,
        sort_by,
    )

"use strict";
/*
 *   Copyright (c) 2025 I.C.Y. B.V.
 *   Author: MerijnHNE
 *   All rights reserved.
 *   This file and code may not be modified, reused, or distributed without the prior written consent of the author or organisation.
 */

require('dotenv').config();
const mysql = require('mysql2/promise');
const fs = require('fs');
const readline = require('readline');
const XLSX = require("xlsx-js-style");
const chalk = require('chalk');
const path = require('path');
const inquirer = require('inquirer');
const { exec } = require('child_process');

// Inquirer UI settings
const INQUIRER_PAGE_SIZE = 12;

async function chooseSchemaInteractive(message = 'Welke database schema (organisatie)?') {
    await fillSchemas();
    const choices = allSchemas.map(s => ({ name: s, value: s }));
    if (choices.length === 0) {
        throw new Error('Geen schema\'s beschikbaar om te kiezen.');
    }
    const answer = await inquirer.prompt([
        { type: 'list', name: 'schema', message: message, choices: choices, pageSize: INQUIRER_PAGE_SIZE }
    ]);
    return answer.schema;
}
const EXPORT_DIR = "C:\\Users\\h.nijdam\\Documents\\ICY-Logs";

// Ensure export directory exists
if (!fs.existsSync(EXPORT_DIR)){
    fs.mkdirSync(EXPORT_DIR, { recursive: true });
}

console.clear();

// Removed readline interface as we are switching to inquirer for main interaction
// Keeping it only if needed for specific legacy parts, but better to remove if fully refactoring.
// For now, I will comment it out to avoid conflicts.
/*
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
})
*/

let dbUrl;
let DB_URL_PORT = process.env.DB_URL_PORT;
let dbUsername = process.env.DB_USERNAME;
let dbPassword = process.env.DB_PASSWORD;

// Cached list of schemas
let allSchemas = [];

async function fillSchemas(force = false) {
    if (!force && Array.isArray(allSchemas) && allSchemas.length > 0) return allSchemas;
    if (!dbUrl) throw new Error('Database URL (dbUrl) is not set. Kies eerst een database.');
    const connection = await mysql.createConnection({
        host: dbUrl,
        port: DB_URL_PORT,
        user: dbUsername,
        password: dbPassword,
        ssl: { rejectUnauthorized: false }
    });
    try {
        const [rows] = await connection.query('SHOW DATABASES');
        allSchemas = rows.map(r => r.Database).filter(d => !['information_schema', 'mysql', 'performance_schema', 'sys'].includes(d));
        return allSchemas;
    } finally {
        try { connection.close(); } catch (e) {}
    }
}

async function execute_set_timedtask_allschemes() {
    await fillSchemas();
    console.log("******** ICY4850 HARDWARECHECK TIMEDTASK INSTELLEN BIJ ALLE ORGANISATIES ************")
    try {
        const connection = await mysql.createConnection({
            host: dbUrl,
            port: DB_URL_PORT,
            user: dbUsername,
            password: dbPassword,
            ssl: {
                rejectUnauthorized: false
            }
        });
        for (let schema of allSchemas) {
            if (schema === 'information_schema' || schema === 'mysql' || schema === 'performance_schema' || schema === 'sys') {
                continue;
            }

            /*

            INSERT INTO timedtask ( taskhandle, category, executioninterval, lastexecuted, executiontime, deadline )
            VALUES
            ( "ICY4850HARDWARECHECK",      0,  1440, '1970-01-01 00:00:01', '03:50',  60 );

            */

            try {
                const query_check_exists = `SELECT * FROM ${schema}.timedtask WHERE taskhandle = 'ICY4850HARDWARECHECK'`;
                const [rows] = await connection.query(query_check_exists);
                if (rows.length > 0) {
                    console.log(`Check: ${schema} Heeft al hardware check. Overslaan...`);
                    continue;
                } else {
                    //generate random time between 03:00 and 05:00
                    let hour = Math.floor(Math.random() * 3) + 3;
                    let minute = Math.floor(Math.random() * 60);

                    if (minute > 60) {
                        throw ("Check: Minuut groter dan 60");
                    }

                    let executiontime = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;

                    console.log(`*** ${schema} HEEFT NOG GEEN ICY4850_HARDWARECHECK TIMEDTASK. KRIJGT *EXECUTIONTIME* TIJD ${executiontime}. TOEVOEGEN... ***`);
                    const query_add_timedtask = `INSERT INTO ${schema}.timedtask ( taskhandle, category, executioninterval, lastexecuted, executiontime, deadline )
                                    VALUES
                                    ( "ICY4850HARDWARECHECK",      0,  1440, '1970-01-01 00:00:01', '${executiontime}',  60 );`;
                    // console.log(query_add_timedtask);
                    await connection.query(query_add_timedtask);
                }
            } catch (error) {
                if (error.code === "ER_NO_SUCH_TABLE") {
                    console.log(`************ ${schema} HEEFT GEEN TIMEDTASK TABEL. OVERSLAAN. ************`);
                    continue;
                } else {
                    console.log(error);
                    console.error("!!!!!!!!!!!!!!! NOODSTOP !!!!!!!!!!!!!!!!!!!");
                    process.exit(1);
                }
            }
        }
        connection.close();
    } catch (e) {
        console.error(`${e.message}`);
        if (e.code !== "ER_NO_SUCH_TABLE") {
            console.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! NOODSTOP !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
            process.exit(1);
        }
    }
    console.log("************ KLAAR ************")
    process.exit(0);
}

async function insertIntoSendlist(scheme, priority = 5, sureness = 1, starttime = "1970-01-01 00:00:01", retrystodo = 5, lasttry = "1970-01-01 00:00:01", comment, address, devid, command, msgdata, newpincode = -1, followingid = null) {
    //check validation

    const query_insert_into_sendlist = `INSERT INTO ${scheme}.sendlist (priority, sureness, starttime, retrystodo, lasttry, comment, address, devid, command, msgdata, newpincode, followingid) VALUES (${priority}, ${sureness}, '${starttime}', ${retrystodo}, '${lasttry}', '${comment}', ${address}, ${devid}, ${command}, '${msgdata}', ${newpincode}, ${followingid})`;
    const connection = await mysql.createConnection({
        host: dbUrl,
        port: DB_URL_PORT,
        user: dbUsername,
        password: dbPassword,
        ssl: {
            rejectUnauthorized: false
        }
    });
    try {
        const [result] = await connection.query(query_insert_into_sendlist);
        connection.close();
        return result;
    } catch (e) {
        connection.close();
        console.error("************ FOUTEN INSERT INTO SENDLIST FUNCTION  ************")
        console.log("************ NOODSTOP SCRIPT ************")
        process.exit();
    }

}

async function execute_change_schakelsettings_4850cm(scheme, dryRun = false) {
    if (dryRun) {
        console.log(chalk.bgMagenta.white.bold("!!! DRY RUN MODE ACTIVE - GEEN WIJZIGINGEN WORDEN DOORGEVOERD !!!"));
    }
    let sendlist_add_failed = [];
    const get_all_modules_query = `SELECT * FROM ${scheme}.slavedevice`;
    try {
        //alle modules ophalen
        const connection = await mysql.createConnection({
            host: dbUrl,
            port: DB_URL_PORT,
            user: dbUsername,
            password: dbPassword,
            ssl: {
                rejectUnauthorized: false
            }
        });

        const [rows] = await connection.query(get_all_modules_query);

        for (const campere of rows) {
            if (campere.slavedevid !== 8705) {
                console.log(`Address: ${campere.slaveaddress} | DeviceID: ${campere.slavedevid} | Geen ICY4850CM. Overslaan.`);
                continue;
            }

            let report_sendlist_item;
            try {
                let check = true;
                const curconfig = campere.curconfig;
                const curconfig_firstBytes = curconfig.slice(0, 8);
                const wanted_newtimeoff = "3c"; //60 seconden

                const check_time_now = curconfig.slice(8, 10);
                if (check_time_now === "3c") {
                    console.log(`Address: ${campere.slaveaddress} | Al 60 seconden schakeltijd ingesteld. Overslaan.`);
                    continue;
                }

                const curconfig_lastBytes = curconfig.slice(10, 14);
                const campere_hex_address = campere.slaveaddress.toString(16).padStart(4, '0');
                const slavecommand = "03";
                const controller_command = "3f";

                const sendlist_wanted_config = curconfig_firstBytes + wanted_newtimeoff + curconfig_lastBytes;
                console.log(`Address: ${campere.slaveaddress} | Oud: ${curconfig} | Nieuw: ${sendlist_wanted_config}`);

                /* OVERLEGGEN MET GERARD*/
                // Moet de curr en wanted config ook direct aangepast worden in slavedevice tabel???!!!
                console.log(campere);
                let check_wantedconfig_changed = false;
                try {
                    const wantedconfig_firstbytes = campere.wantedconfig.slice(0, 8);
                    const wantedconfig_lastbytes = campere.wantedconfig.slice(10, 14);
                    const new_wantedconfig = wantedconfig_firstbytes + wanted_newtimeoff + wantedconfig_lastbytes;
                    /*
                        CHECKEN OF HET KLOPT
                        Oud:    01 00 00 a0 1e 0a 18 -> 30 seconden
                        Nieuw:  01 00 00 a0 3c 0a 18 -> 60 seconden
                        KLOPT
                    */

                    const query_change_wantedconfig = `UPDATE ${scheme}.slavedevice SET wantedconfig = '${new_wantedconfig}' WHERE slaveaddress = ${campere.slaveaddress}`;
                    if (!dryRun) {
                        await connection.query(query_change_wantedconfig);
                        check_wantedconfig_changed = true;
                    } else {
                        console.log(chalk.magenta(`[DRY RUN] Zou uitvoeren: ${query_change_wantedconfig}`));
                        check_wantedconfig_changed = true; // Simulate success
                    }
                } catch (error) {
                    console.error("********** FOUT BIJ AANPASSEN WANTEDCONFIG TABEL SLAVEDEVICE **********");
                    console.error(error);
                }

                //Hetzelfde doen we bij de unoccupiedconfig
                let check_unoccupiedconfig_changed = false;
                try {
                    const unoccupiedconfig_firstbytes = campere.unoccupiedconfig.slice(0, 8);
                    const unoccupiedconfig_lastbytes = campere.unoccupiedconfig.slice(10, 14);
                    const new_unoccupiedconfig = unoccupiedconfig_firstbytes + wanted_newtimeoff + unoccupiedconfig_lastbytes;

                    const query_change_unoccupiedconfig = `UPDATE ${scheme}.slavedevice SET unoccupiedconfig = '${new_unoccupiedconfig}' WHERE slaveaddress = ${campere.slaveaddress}`;
                    if (!dryRun) {
                        await connection.query(query_change_unoccupiedconfig);
                        check_unoccupiedconfig_changed = true;
                    } else {
                        console.log(chalk.magenta(`[DRY RUN] Zou uitvoeren: ${query_change_unoccupiedconfig}`));
                        check_unoccupiedconfig_changed = true; // Simulate success
                    }
                    /*
                        CONTROLEN CHECKEN OF HET KLOPT
                        Oud:      01 00 00 a0 1e 0a 18
                        Nieuw:    01 00 00 a0 3c 0a 18
                        KLOPT!
                    */
                } catch (error) {
                    console.error("********** FOUT BIJ AANPASSEN UNOCCUPIEDCONFIG TABEL SLAVEDEVICE **********");
                    console.error(error);
                }

                //Get deviceadress controller by deviceID
                const query_deviceaddress_controller = `SELECT address,devid FROM ${scheme}.device WHERE deviceid = ${campere.deviceid}`;
                let controller_data = await connection.query(query_deviceaddress_controller);
                let controller_address;
                let controller_devid;
                let new_msgdata;
                if (controller_data[0].length === 0) {
                    console.error("********** GEEN CONTROLLER GEVONDEN VOOR MODULE ADDRESS" + campere.slaveaddress + ". SLAAT OVER! **********")
                    check = false;
                } else {
                    controller_address = controller_data[0][0].address;
                    controller_devid = controller_data[0][0].devid;


                    new_msgdata = campere_hex_address + slavecommand + sendlist_wanted_config;
                }

                report_sendlist_item = {
                    scheme: scheme,
                    slavedeviceid: campere.slavedeviceid,
                    slaveaddress: campere.slaveaddress,
                    old_config: curconfig,
                    new_config: sendlist_wanted_config,
                    controller_address: controller_address,
                    sendlist_add: {
                        controller_address: controller_address,
                        controller_devid: controller_devid,
                        command: controller_command,
                        msgdata: new_msgdata
                    },
                    campere: campere
                }
                /*

                1 02 03 01 00 00 a0 3c 0a 18 <-- FOUT!

                */

                if (check === false || check_wantedconfig_changed === false || check_unoccupiedconfig_changed === false) {
                    console.log("Checks failed, niet toevoegen aan sendlist");
                    console.error("************* MODULE STOP | CHECK IS FALSE  ************");
                    sendlist_add_failed.push(report_sendlist_item)
                    continue;
                }

                if (new_msgdata.length !== 20) check = false; //NIET UITVOEREN!!
                if (!controller_address) check = false; //NIET UITVOEREN!!
                if (!controller_devid) check = false; //NIET UITVOEREN!!
                if (campere_hex_address.length > 4) check = false; //NIET UITVOEREN!!

                if (check === true || check_wantedconfig_changed === true || check_unoccupiedconfig_changed === true) {
                    if (!dryRun) {
                        let result = await insertIntoSendlist(scheme, 30, 1, "1970-01-01 00:00:01", 5, "1970-01-01 00:00:01", "force config campere by icy", parseInt(controller_address, 10), parseInt(controller_devid, 10), parseInt(controller_command, 16), new_msgdata, -1, null);
                    } else {
                        console.log(chalk.magenta(`[DRY RUN] Zou uitvoeren: insertIntoSendlist(...) voor module ${campere.slaveaddress}`));
                    }
                } else {
                    console.log("Check failed, niet toevoegen aan sendlist");
                    console.error("************* MODULE STOP | CHECK IS FALSE  ************");
                    sendlist_add_failed.push(report_sendlist_item)
                }
                /*
                070000a00a0a18
                07 00 00 a0 0a 0a 18
                1  2  3  4  5  6  7
                            ^
                            |
                Moet naar 3C

                Test:
                07 00 00 a0 0a 0a 18
                07 00 00 a0 3c 0a 18
                KLOPT
                */
            } catch (e) {
                sendlist_add_failed.push(report_sendlist_item)
                console.log("ERROR: " + e.message);
                console.log(e);
                continue;
            }
        }
        console.log("************ KLAAR. ************");
        if (sendlist_add_failed.length === 0) {
            console.log("Voor alle modules is een opdracht in sendlist toegevoegd.")
        } else {
            console.log(sendlist_add_failed);
            console.log("BOVENSTAANDE WERDEN UIT VEILIGHEID NIET TOEGEVOEGD AAN DE SENDLIST.");
            console.log(`Aantal: ${sendlist_add_failed.length}`);
        }
        console.log("****** BEËINDIGD ******")
        process.exit(0);

    } catch (e) {
        console.error("************ FOUTEN MET CONNECTIE DATABASE ************");
        console.log(e.message);
        console.log("************** BEËINDIGD *************")
        process.exit(0);
    }
}

async function uitdraai_schakeltijden_4850() {
    try {

        await fillSchemas();
        const connection = await mysql.createConnection({
            host: dbUrl,
            port: DB_URL_PORT,
            user: dbUsername,
            password: dbPassword,
            ssl: {
                rejectUnauthorized: false
            }
        });

        let to_report = [];
        for (let schema of allSchemas) {
            try {
                const [rows] = await connection.query(`SELECT * FROM ${schema}.slavedevice WHERE slavedevid = 8705`);

                let index_scanned_modules = 0;
                let controle_array = [];
                for (const row of rows) {
                    index_scanned_modules++;
                    const schakeltijd_hex = row.curconfig.slice(8, 10);
                    let schakeltijd_dec = parseInt(schakeltijd_hex, 16);
                    if (schakeltijd_dec < 60) {
                        controle_array.push(schakeltijd_dec);
                    }
                }

                //Maak een string zoals: be_memling: Laagste seconden: XX | Hoogste seconden: XX |
                if (controle_array.length > 0) {
                    const laagste_seconden = Math.min(...controle_array);
                    const hoogste_seconden = Math.max(...controle_array);
                    console.log(chalk.magenta(`${schema}: Laagste seconden: ${laagste_seconden} | Hoogste seconden: ${hoogste_seconden} |`));

                    to_report.push({
                        schema: schema,
                        Laagste_seconden: laagste_seconden,
                        Hoogste_seconden: hoogste_seconden,
                        scanned_modules: index_scanned_modules
                    });
                }

            } catch (error) {
                if (error.code === "ER_NO_SUCH_TABLE") {
                    continue;
                }
                console.error(`Error`, error);
            }
        }
        //Maak een excel bestand en sla resultaat op

        const ws = XLSX.utils.json_to_sheet(to_report);

        // Headers bold maken en styling toepassen
        if (to_report.length > 0) {
            const range = XLSX.utils.decode_range(ws['!ref']);
            for (let col = range.s.c; col <= range.e.c; col++) {
                const cellAddress = XLSX.utils.encode_cell({ r: 0, c: col });
                if (!ws[cellAddress]) continue;
                ws[cellAddress].s = {
                    font: { bold: true, sz: 11 },
                    alignment: { vertical: 'center', horizontal: 'left' }
                };
            }
        }

        // AutoFilter toevoegen
        if (to_report.length > 0) {
            const range = XLSX.utils.decode_range(ws['!ref']);
            ws['!autofilter'] = { ref: XLSX.utils.encode_range(range) };

            // Kolombreedtes instellen
            ws['!cols'] = [
                { wch: 30 }, // schema
                { wch: 20 }, // Laagste_seconden
                { wch: 20 }, // Hoogste_seconden
                { wch: 20 }  // scanned_modules
            ];
        }

        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Schakeltijden 4850CM");
        const filename = `icy4850cm_schakeltijden_rapport_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.xlsx`;
        const fullPath = path.join(EXPORT_DIR, filename);
        XLSX.writeFile(wb, fullPath, { cellStyles: true });
        console.log(`RAPPORTAGE OPSLAAN GELUKT: ${fullPath}`);

        const openAnswer = await inquirer.prompt([
            { type: 'confirm', name: 'open', message: 'Bestand openen?', default: true }
        ]);

        if (openAnswer.open) {
            await openFile(fullPath);
        }

        connection.close();
    } catch (error) {
        console.log("Error", error);
    }
    console.log("=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=");
    console.log("Bovenstaande parken hebben tenminste 1 module met een schakeltijd onder de 60 seconden.");
    console.log("Parken met meer dan 60 seconden schakeltijd worden niet gerapporteerd.");
    console.log("************ KLAAR ************")
    process.exit(0);
}

async function execute_enabled_check() {
    await fillSchemas();
    try {
        const connection = await mysql.createConnection({
            host: dbUrl,
            port: DB_URL_PORT,
            user: dbUsername,
            password: dbPassword,
            ssl: {
                rejectUnauthorized: false
            }
        });
        for (let schema of allSchemas) {


            if (schema === 'information_schema' || schema === 'mysql' || schema === 'performance_schema' || schema === 'sys') {
                continue;
            }

            //Check if already category ICY4850HARDWARECHECK id ENABLE exitst in schema.settings
            try {

                const query_check_exists = `SELECT * FROM ${schema}.settings WHERE category = 'ICY4850HARDWARECHECK' AND id = 'ENABLE'`;
                const [rows] = await connection.query(query_check_exists);
                if (rows.length > 0) {
                    if (rows[0].value === "true") {
                        console.log(chalk.green(`${schema}: High Resolution Measurement Hardwarecheck is INGESCHAKELD.`));
                    } else {
                        console.log(chalk.red(`${schema}: High Resolution Measurement Hardwarecheck is UITGESCHAKELD.`));
                    }
                } else {
                    console.log(chalk.yellow(`${schema}: Heeft nog geen ICY4850HARDWARECHECK settings.`));
                }
            } catch (e) {
                console.error(chalk.red(`!!!!!!!!!!!!!!!! FOUT BIJ SCHEMA ${schema}: ${e.message} !!!!!!!!!!!!!!!!`));
            }
        }
        connection.close();
    } catch (error) {
        console.error(error);
        console.error("!!!!!!!!!!!!!!! NOODSTOP !!!!!!!!!!!!!!!!!!!");
        process.exit(1);
    }
    console.log("************ KLAAR ************")
    process.exit(0);
}

// Add standard settings to all schemas (with dryRun support)
async function execute_add_settings(dryRun = false) {
    await fillSchemas();
    console.log(chalk.bold.blue('************ SETTINGS TOEVOEGEN AAN ALLE ORGANISATIES ************'));
    console.log(chalk.yellow('Controleren of setting ICY4850HARDWARECHECK (ENABLE) aanwezig is per schema.'));

    try {
        const connection = await mysql.createConnection({
            host: dbUrl,
            port: DB_URL_PORT,
            user: dbUsername,
            password: dbPassword,
            ssl: { rejectUnauthorized: false }
        });

        for (const schema of allSchemas) {
            if (['information_schema', 'mysql', 'performance_schema', 'sys'].includes(schema)) continue;
            try {
                const query_check = `SELECT * FROM ${schema}.settings WHERE category = 'ICY4850HARDWARECHECK' AND id = 'ENABLE' LIMIT 1`;
                const [rows] = await connection.query(query_check);
                if (rows.length > 0) {
                    console.log(chalk.gray(`${schema}: setting bestaat al. Overslaan.`));
                    continue;
                }

                const insertQuery = `INSERT INTO ${schema}.settings (category, id, value) VALUES ('ICY4850HARDWARECHECK','ENABLE','true')`;
                if (dryRun) {
                    console.log(chalk.magenta(`[DRY RUN] ${schema}: zou uitvoeren: ${insertQuery}`));
                } else {
                    try {
                        await connection.query(insertQuery);
                        console.log(chalk.green(`${schema}: setting toegevoegd.`));
                    } catch (e) {
                        if (e.code === 'ER_NO_SUCH_TABLE') {
                            console.log(chalk.yellow(`${schema}: heeft geen \'settings\' tabel. Overslaan.`));
                        } else {
                            console.log(chalk.red(`${schema}: fout bij toevoegen setting: ${e.message}`));
                        }
                    }
                }

            } catch (e) {
                if (e.code === 'ER_NO_SUCH_TABLE') {
                    console.log(chalk.yellow(`${schema}: heeft geen \'settings\' tabel. Overslaan.`));
                    continue;
                }
                console.log(chalk.red(`${schema}: fout bij controle: ${e.message}`));
            }
        }

        try { connection.close(); } catch (e) {}
    } catch (err) {
        console.error(chalk.red('Fout bij verbinden met database: ' + err.message));
        process.exit(1);
    }

    console.log(chalk.bold.green('************ KLAAR ************'));
    process.exit(0);
}

function formatTimestamp(ts) {
    // Zorg dat ts een Date object is
    const d = new Date(ts);

    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');

    return `${yyyy}-${mm}-${dd} ${hh}-${min}-${ss}`;
}

function openFile(filePath) {
    return new Promise((resolve) => {
        const command = process.platform === 'win32' ? `start "" "${filePath}"` : `open "${filePath}"`;
        require('child_process').exec(command, (error) => {
            if (error) {
                console.error("Fout bij openen bestand:", error);
            }
            // We wachten kort om zeker te zijn dat het commando is afgevuurd
            setTimeout(resolve, 500);
        });
    });
}

let to_report = [];
async function get_status_per_park() {
    //We halen alle parken op
    await fillSchemas();
    const connection = await mysql.createConnection({
        host: dbUrl,
        port: DB_URL_PORT,
        user: dbUsername,
        password: dbPassword,
        ssl: {
            rejectUnauthorized: false
        }
    });

    let i = 0;
    console.log(`***** Checks uitvoeren alle parken *****`);
    for (const scheme of allSchemas) {
        i++
        to_report.push({ schema: scheme, issues: [] });

        const sql_get_sd = `SELECT * FROM ${scheme}.icy4850hardwareissue WHERE state != "STATUS_OK"`;
        // console.log(sql_get_sd);

        //We gaan dit uitvoeren
        try {
            let already_checked = [];
            const [rows] = await connection.query(sql_get_sd);
            // console.log(rows);
            for (const meting of rows) {
                if (already_checked.includes(meting.slaveaddress)) {
                    continue;
                } else {
                    already_checked.push(meting.slaveaddress);
                }

                const sql_get_last_measurement = `SELECT * FROM ${scheme}.icy4850hardwareissue WHERE slaveaddress = ${meting.slaveaddress} ORDER BY timestamp DESC LIMIT 1`;
                let [last_measurement] = await connection.query(sql_get_last_measurement);
                last_measurement = last_measurement[0];
                // console.log(last_measurement);

                const sql_check_replaced = `SELECT * FROM ${scheme}.slavedevice WHERE slaveaddress = ${meting.slaveaddress}`;
                let [check_replaced] = await connection.query(sql_check_replaced);
                if (check_replaced.length === 0) {
                    // console.log(`|||| ${scheme} | Address: ${meting.slaveaddress} | Module al vervangen. Rapporteren niet nodig. ||||`);
                    continue; //Module is vervangen, niet rapporteren.
                }

                if (last_measurement.state === "STATUS_OK") { //Laatste meting is oke, rapporteren we niet.
                    continue;
                } else {
                    let report_object = {
                        scheme: scheme,
                        address: last_measurement.slaveaddress,
                        state_now: last_measurement.state,
                        highresolutionmeasurement_last: last_measurement,
                        highresolutionmeasurement_first: meting
                    }
                    to_report[i - 1].issues.push(report_object); //Rapporteer deze module voor de organisatie

                    const msg = `${scheme} | Address: ${last_measurement.slaveaddress} | STATUS: ${last_measurement.state} | Current: ${last_measurement.currentrms}A | Power: ${last_measurement.activepower}W | Timestamp: ${last_measurement.timestamp}`;
                    switch (last_measurement.state) {
                        case "STATUS_UNRELIABLE":
                            console.log(chalk.yellow(`[VERDACHT] ${msg}`));
                            break;
                        case "STATUS_DEFECT":
                            console.log(chalk.red(`[DEFECT] ${msg}`));
                            break;
                        case null:
                            console.log(chalk.blue(`[PREMATURE] ${msg}`));
                            break;
                        default:
                            console.log(chalk.gray(`[ONBEKEND] ${msg}`));
                            break;
                    }
                }

            }

        } catch (e) {
            if (e.code !== "ER_NO_SUCH_TABLE") {
                console.error(chalk.red(`FOUT BIJ OPHALEN MODULES VAN SCHEMA ${scheme}: ${e.message}`));
            }
            continue;
        }
        // break;
    }
    // try {
    //     connection.close();
    //     console.log("************ KLAAR ************");

    //     let wsr = "";
    //     let report_time = new Date()
    //         .toISOString()
    //         .slice(0, 19)        // yyyy-mm-ddThh:mm:ss
    //         .replace("T", " ")   // yyyy-mm-dd hh:mm:ss
    //         .replace(/:/g, "-"); // yyyy-mm-dd hh-mm-ss

    //     console.log(report_time);
    //     wsr += `ICY4850CM Hardware Issue Check Rapport (High Resolution Measurement)\n`;
    //     wsr += `Rapportage tijd: ${report_time}\n`;
    //     wsr += `Database: ${dbUrl}\n`;
    //     wsr += `Rapporteert alle modules die **NU** verdacht of defect zijn van alle organisaties en die nog NIET vervangen zijn.\n`;
    //     wsr += `Een status null is een premature check.\n`;

    //     for (const report of to_report) {
    //         if (report.issues.length === 0) continue;
    //         //address naar HEX:
    //         wsr += `\n`;
    //         wsr += `Schema: ${report.schema}`;

    //         for (const issue of report.issues) {
    //             //address naar HEX:
    //             const address_hex = issue.address.toString(16).padStart(4, '0').toUpperCase();
    //             wsr += `\n   Address: ${issue.address} (${address_hex}): HUIDIGE STATUS: ${issue.state_now}\n`;
    //             wsr += `      << First measurement: Timestamp: ${formatTimestamp(issue.highresolutionmeasurement_first.timestamp)}: Current: ${issue.highresolutionmeasurement_first.currentrms}A: Power: ${issue.highresolutionmeasurement_first.activepower}W: Status meting: ${issue.highresolutionmeasurement_first.state}\n`;
    //             wsr += `      >> Last measurement: Timestamp: ${formatTimestamp(issue.highresolutionmeasurement_last.timestamp)}: Current: ${issue.highresolutionmeasurement_last.currentrms}A: Power: ${issue.highresolutionmeasurement_last.activepower}W: Status meting: ${issue.highresolutionmeasurement_last.state}\n`;
    //         }
    //     }

    //     const filename = `icy4850_hrm_rapport_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;

    //     await fs.promises.writeFile(filename, wsr, "utf8");

    //     console.log(`RAPPORTAGE OPSLAAN GELUKT: ${filename}`);
    // } catch (error) {
    //     console.log("************* FOUT BIJ OPSLAAN ************");
    //     console.log(error);
    // }
    try {
        connection.close();
        console.log(chalk.green("************ KLAAR ************"));

        const report_time = new Date()
            .toISOString()
            .slice(0, 19)
            .replace(/[:T]/g, "-");

        const rows = [];

        for (const report of to_report) {
            if (report.issues.length === 0) continue;

            for (const issue of report.issues) {
                const address_hex = issue.address
                    .toString(16)
                    .padStart(4, "0")
                    .toUpperCase();

                rows.push({
                    "Rapportage tijd": report_time,
                    Schema: report.schema,
                    Address: `${issue.address} (${address_hex})`,
                    "State now": issue.state_now || "N/A",
                    "First Timestamp": issue.highresolutionmeasurement_first?.timestamp ? formatTimestamp(issue.highresolutionmeasurement_first.timestamp) : "N/A",
                    "First Current": issue.highresolutionmeasurement_first?.currentrms ?? "N/A",
                    "First Power": issue.highresolutionmeasurement_first?.activepower ?? "N/A",
                    "First State": issue.highresolutionmeasurement_first?.state ?? "N/A",
                    "Last Timestamp": issue.highresolutionmeasurement_last?.timestamp ? formatTimestamp(issue.highresolutionmeasurement_last.timestamp) : "N/A",
                    "Last Current": issue.highresolutionmeasurement_last?.currentrms ?? "N/A",
                    "Last Power": issue.highresolutionmeasurement_last?.activepower ?? "N/A",
                    "Last State": issue.highresolutionmeasurement_last?.state ?? "N/A"
                });
            }
        }

        // Zet data om naar een werkblad
        const ws = XLSX.utils.json_to_sheet(rows);

        // Headers bold maken
        if (rows.length > 0) {
            const range = XLSX.utils.decode_range(ws['!ref']);
            for (let col = range.s.c; col <= range.e.c; col++) {
                const cellAddress = XLSX.utils.encode_cell({ r: 0, c: col });
                if (!ws[cellAddress]) continue;
                ws[cellAddress].s = {
                    font: { bold: true, sz: 11 },
                    alignment: { vertical: 'center', horizontal: 'left' }
                };
            }
        }

        // AutoFilter toevoegen (zoals in screenshot)
        if (rows.length > 0) {
            const range = XLSX.utils.decode_range(ws['!ref']);
            ws['!autofilter'] = { ref: XLSX.utils.encode_range(range) };

            // Kolombreedtes instellen voor betere leesbaarheid
            ws['!cols'] = [
                { wch: 22 }, // Rapportage_tijd
                { wch: 25 }, // Schema
                { wch: 18 }, // Address
                { wch: 20 }, // State_now
                { wch: 22 }, // First_Timestamp
                { wch: 15 }, // First_Current
                { wch: 15 }, // First_Power
                { wch: 20 }, // First_State
                { wch: 22 }, // Last_Timestamp
                { wch: 15 }, // Last_Current
                { wch: 15 }, // Last_Power
                { wch: 20 }  // Last_State
            ];
        }

        // Maak een nieuwe workbook
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Rapport");

        // Schrijf naar bestand MET cellStyles optie
        const filename = `icy4850_hrm_rapport_${report_time}.xlsx`;
        const fullPath = path.join(EXPORT_DIR, filename);
        XLSX.writeFile(wb, fullPath, { cellStyles: true });

        console.log(`RAPPORTAGE OPSLAAN GELUKT: ${fullPath}`);

        const openAnswer = await inquirer.prompt([
            { type: 'confirm', name: 'open', message: 'Bestand openen?', default: true }
        ]);

        if (openAnswer.open) {
            await openFile(fullPath);
        }

    } catch (error) {
        console.log("************* FOUT BIJ OPSLAAN ************");
        console.log(error);
    }
    console.log(chalk.green("****** BEËINDIGD ******"));
    process.exit(0);
}

// Scan alle schemas op modules met schakeltijd < 60 seconden
async function execute_check_and_offer_convert_schakeltijden_all(interactive = true) {
    await fillSchemas();
    console.log(chalk.bold.blue('************ CHECK SCHAKELTIJDEN (ALLE ORGANISATIES) ************'));

    const connection = await mysql.createConnection({
        host: dbUrl,
        port: DB_URL_PORT,
        user: dbUsername,
        password: dbPassword,
        ssl: { rejectUnauthorized: false }
    });

    const schemasWithShortTimes = [];

    for (const schema of allSchemas) {
        if (['information_schema', 'mysql', 'performance_schema', 'sys'].includes(schema)) continue;
        try {
            const [rows] = await connection.query(`SELECT slaveaddress, slavedevid, curconfig, slavedeviceid FROM ${schema}.slavedevice WHERE slavedevid = 8705`);
            const problematic = [];
            for (const r of rows) {
                try {
                    if (!r.curconfig || r.curconfig.length < 10) continue;
                    const hex = r.curconfig.slice(8, 10);
                    const sec = parseInt(hex, 16);
                    if (!Number.isNaN(sec) && sec < 60) {
                        problematic.push({ slaveaddress: r.slaveaddress, seconds: sec, slavedeviceid: r.slavedeviceid });
                    }
                } catch (e) {
                    continue;
                }
            }
            if (problematic.length > 0) {
                schemasWithShortTimes.push({ schema, count: problematic.length, details: problematic });
                console.log(chalk.yellow(`${schema}: ${problematic.length} module(s) met schakeltijd < 60s`));
            } else {
                console.log(chalk.gray(`${schema}: geen modules met schakeltijd < 60s`));
            }
        } catch (e) {
            if (e.code === 'ER_NO_SUCH_TABLE') continue;
            console.error(chalk.red(`Fout bij schema ${schema}: ${e.message}`));
        }
    }

    try { connection.close(); } catch (e) {}

    if (schemasWithShortTimes.length === 0) {
        console.log(chalk.green('Geen organisaties gevonden met modules met schakeltijd < 60 seconden.'));
        if (interactive) process.exit(0);
        return;
    }

    // Bied optie om scan-resultaten te exporteren naar Excel
    try {
        const exportAnswer = await inquirer.prompt([{ type: 'confirm', name: 'export', message: 'Resultaten exporteren naar Excel?', default: true }]);
        if (exportAnswer.export) {
            const rows = [];
            for (const s of schemasWithShortTimes) {
                for (const d of s.details) {
                    rows.push({ Schema: s.schema, SlaveAddress: d.slaveaddress, Seconds: d.seconds, Slavedeviceid: d.slavedeviceid });
                }
            }

            const ws = XLSX.utils.json_to_sheet(rows);
            if (rows.length > 0 && ws['!ref']) {
                const range = XLSX.utils.decode_range(ws['!ref']);
                for (let col = range.s.c; col <= range.e.c; col++) {
                    const cellAddress = XLSX.utils.encode_cell({ r: 0, c: col });
                    if (!ws[cellAddress]) continue;
                    ws[cellAddress].s = { font: { bold: true, sz: 11 }, alignment: { vertical: 'center', horizontal: 'left' } };
                }
                ws['!autofilter'] = { ref: XLSX.utils.encode_range(range) };
            }

            const wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, ws, 'ScanResultaten');
            const filename = `icy4850_schakeltijden_scan_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.xlsx`;
            const fullPath = path.join(EXPORT_DIR, filename);
            XLSX.writeFile(wb, fullPath, { cellStyles: true });
            console.log(`RAPPORTAGE OPSLAAN GELUKT: ${fullPath}`);

            const openAnswer = await inquirer.prompt([{ type: 'confirm', name: 'open', message: 'Bestand openen?', default: true }]);
            if (openAnswer.open) await openFile(fullPath);
        }
    } catch (e) {
        console.error(chalk.red('Fout bij exporteren:'), e.message || e);
    }

    // Interactive: bied keuze om te converteren
    if (interactive) {
        const choices = schemasWithShortTimes.map(s => ({ name: `${s.schema} (${s.count} modules)`, value: s.schema }));
        const answer = await inquirer.prompt([
            { type: 'checkbox', name: 'selected', message: 'Kies organisatie(s) om modules om te zetten naar 60 seconden (via sendlist):', choices: choices, pageSize: INQUIRER_PAGE_SIZE }
        ]);

        if (!answer.selected || answer.selected.length === 0) {
            console.log(chalk.yellow('Geen organisaties geselecteerd. Beëindigen.'));
            process.exit(0);
        }

        const dryRunAnswer = await inquirer.prompt([
            { type: 'list', name: 'mode', message: 'Kies uitvoermodus:', choices: [ { name: 'Dry Run (simulatie)', value: true }, { name: 'Live (voer wijzigingen uit)', value: false } ], pageSize: INQUIRER_PAGE_SIZE }
        ]);

        console.log(`Geselecteerde organisaties: ${answer.selected.join(', ')}`);
        if (dryRunAnswer.mode) console.log(chalk.magenta('MODUS: DRY RUN (geen wijzigingen)'));

        const confirm = await inquirer.prompt([{ type: 'confirm', name: 'ok', message: 'Weet je zeker dat je wilt doorgaan?', default: false }]);
        if (!confirm.ok) process.exit(0);

        for (const sch of answer.selected) {
            console.log(chalk.blue(`-- Uitvoeren voor schema: ${sch} --`));
            try {
                await execute_change_schakelsettings_4850cm(sch, dryRunAnswer.mode);
            } catch (e) {
                console.error(chalk.red(`Fout bij verwerken ${sch}: ${e.message}`));
            }
        }
    }
}

function perform_search(answer) {
    try {
        const regex = new RegExp(answer, 'i'); // Case insensitive
        const matches = allSchemas.filter(schema => regex.test(schema));

        console.log(chalk.green(`Gevonden resultaten (${matches.length}):`));
        matches.forEach(match => {
            // Highlight the match
            const matchResult = match.match(regex);
            if (matchResult) {
                const highlighted = match.replace(regex, (m) => chalk.bgYellow.black(m));
                console.log(`- ${highlighted}`);
            } else {
                console.log(`- ${match}`);
            }
        });
    } catch (e) {
        console.log(chalk.red("Ongeldige Regex: " + e.message));
    }
}

async function search_organizations() {
    await fillSchemas();
    console.log(chalk.cyan("************ ZOEK ORGANISATIE ************"));
    const answer = await inquirer.prompt([
        { type: 'input', name: 'term', message: 'Zoekterm (Regex ondersteund):' }
    ]);
    perform_search(answer.term);
    console.log(chalk.cyan("************ KLAAR ************"));
    process.exit(0);
}

async function execute() {
    console.log(chalk.bold.blue("************ STARTUP 4850CM DB TOOLS ************"))

    if (!process.env.DB_URL1 || !process.env.DB_URL2 || !process.env.DB_URL_PORT || !process.env.DB_USERNAME || !process.env.DB_PASSWORD) {
        console.error(chalk.red("************ FOUT: GEEN DATABASE GEGEVENS AANWEZIG IN .ENV BESTAND ************"))
        console.log(chalk.red("************ BEËINDIGD ************"))
        process.exit(1);
    }

    // WORKER MODE
    if (process.argv.length > 2) {
        const dbChoice = (process.argv[2] || '').toUpperCase();
        const actionChoice = (process.argv[3] || '').toUpperCase();
        const extraArg = process.argv[4];
        const extraArg2 = process.argv[5];

        console.log(chalk.magenta(`Worker Mode: DB=${dbChoice}, Action=${actionChoice}`));

        // select DB URL based on choice
        if (dbChoice === "A") {
            dbUrl = process.env.DB_URL1;
        } else if (dbChoice === "B") {
            dbUrl = process.env.DB_URL2;
        } else {
            console.error(chalk.red(`Onbekende database keuze: ${dbChoice}`));
            process.exit(1);
        }

        // handle actionChoice independently
        if (actionChoice === 'A') {
            await execute_set_timedtask_allschemes();
        } else if (actionChoice === 'B') {
            await execute_add_settings();
        } else if (actionChoice === 'C') {
            // schema may be provided as extraArg, else prompt
            const schemaArg = extraArg;
            let schema = schemaArg;
            if (!schema) {
                try {
                    schema = await chooseSchemaInteractive();
                } catch (e) {
                    console.error(chalk.red('Kon geen organisatie kiezen: ' + e.message));
                    process.exit(1);
                }
            }
            const dryRunFlag = (typeof extraArg2 !== 'undefined') ? (extraArg2 === 'true' || extraArg2 === '1') : false;
            await execute_change_schakelsettings_4850cm(schema, dryRunFlag);
        } else if (actionChoice === 'D') {
            await execute_enabled_check();
        } else if (actionChoice === 'E') {
            await get_status_per_park();
        } else if (actionChoice === 'F') {
            console.log(chalk.bold.blue("************ SCHAKELTIJD AANPASSEN MODULES ************"));
            console.log("Je gaat nu de modules aanpassen naar 60 seconden schakeltijd via de sendlist van een organisatie.");

            const schemaAnswer = await inquirer.prompt([
                { type: 'input', name: 'schema', message: 'Welke database schema (organisatie)?' }
            ]);

            const dryRunAnswer = await inquirer.prompt([
                {
                    type: 'list',
                    name: 'mode',
                    message: 'Kies uitvoer modus:',
                    choices: [
                        { name: 'Dry Run (Veilig - Alleen simuleren)', value: true },
                        { name: 'Live (LET OP: Wijzigingen worden doorgevoerd!)', value: false }
                    ],
                    pageSize: INQUIRER_PAGE_SIZE
                }
            ]);

            console.log(`Je gaat nu de sendlist vullen voor organisatie: ${schemaAnswer.schema}.`);
            if(dryRunAnswer.mode) console.log(chalk.magenta("MODUS: DRY RUN (Geen wijzigingen)"));
            else console.log(chalk.red("MODUS: LIVE (Wijzigingen worden opgeslagen!)"));

            const confirm = await inquirer.prompt([{ type: 'confirm', name: 'ok', message: 'Weet je het zeker?', default: false }] );

            if (confirm.ok) {
                await execute_change_schakelsettings_4850cm(schemaAnswer.schema, dryRunAnswer.mode);
            } else {
                process.exit(0);
            }

        } else if (actionChoice === 'G') {
            const searchAnswer = await inquirer.prompt([{ type: 'input', name: 'term', message: 'Zoekterm (Regex ondersteund):' }]);
            if (!searchAnswer.term) { console.log(chalk.red('Geen zoekterm opgegeven.')); process.exit(0); }
            await fillSchemas();
            perform_search(searchAnswer.term);
            console.log(chalk.cyan("************ KLAAR ************"));
            process.exit(0);
        } else if (actionChoice === 'H') {
            // non-interactive scan/report mode for schakeltijden
            await execute_check_and_offer_convert_schakeltijden_all(false);
        } else {
            console.error(chalk.red(`Onbekende actie: ${actionChoice}`));
            process.exit(1);
        }
        return;
    }


    // INTERACTIVE MODE WITH INQUIRER (loopable menus, Q = terug, X = afsluiten)
    try {
        while (true) {
            const dbAnswer = await inquirer.prompt([
                {
                    type: 'list',
                    name: 'database',
                    message: 'Selecteer database:',
                    choices: [
                        { name: 'MySQL Database (icyccdb.icy.nl)', value: 'A' },
                        { name: 'MariaDB Database (icyccdb02.icy.nl)', value: 'B' },
                        { name: 'README.MD weergeven', value: 'C' },
                        { name: 'X: Afsluiten', value: 'X' }
                    ],
                    pageSize: INQUIRER_PAGE_SIZE
                }
            ]);

            if (dbAnswer.database === 'X') {
                console.log(chalk.yellow('Afsluiten.'));
                process.exit(0);
            }

            if (dbAnswer.database === 'C') {
                try {
                    const readmeContent = fs.readFileSync('README.md', 'utf8');
                    console.log(chalk.white(readmeContent));
                } catch (e) {
                    console.error(chalk.red("Kon README.md niet lezen: " + e.message));
                }
                continue; // terug naar database selectie
            }

            if (dbAnswer.database === 'A') {
                console.log(chalk.green("=-= MySQL Database geselecteerd =-="));
                dbUrl = process.env.DB_URL1;
            } else if (dbAnswer.database === 'B') {
                console.log(chalk.green("=-= MariaDB Database geselecteerd =-="));
                dbUrl = process.env.DB_URL2;
            }

            // inner action loop
            let backToDb = false;
            while (!backToDb) {
                const actionAnswer = await inquirer.prompt([
                    {
                        type: 'list',
                        name: 'action',
                        message: 'Wat gaan we doen?',
                        choices: [
                            { name: 'A: (!) Timedtask toevoegen alle organisaties', value: 'A' },
                            { name: 'B: (!) Settings toevoegen alle organisaties', value: 'B' },
                            { name: 'C: (!) Modules omzetten naar 60 seconden schakeltijd (sendlist) voor 1 organisatie', value: 'C' },
                            { name: 'D: Check de timedtask van setting ICY4850HARDWARECHECK per organisatie', value: 'D' },
                            { name: 'E: Rapport & huidige status ICY4850HARDWAREISSUE per organisatie', value: 'E' },
                            { name: 'F: Rapport & huidige status (min & max) ICY4850CM per organisatie', value: 'F' },
                            { name: 'G: Zoek organisatie (Regex)', value: 'G' },
                            { name: 'H: Check & wijzig schakeltijden (alle organisaties)', value: 'H' },
                            { name: 'Q: Terug naar Database Selectie', value: 'Q' }
                        ],
                        pageSize: INQUIRER_PAGE_SIZE
                    }
                ]);

                const action = actionAnswer.action;
                if (action === 'Q') { backToDb = true; continue; }

                if (action === 'A') {
                    console.log(chalk.bold.blue("************ TIMEDTASK TOEVOEGEN ************"));
                    console.log(chalk.yellow("=-=-= CONTROLEER DE TIMEDTASK IN DE CODE HARDCODED OF DEZE NU NOG VAN TOEPASSING ZIJN =-=-="));
                    const confirm = await inquirer.prompt([{ type: 'confirm', name: 'ok', message: 'Doorgaan?', default: false }]);
                    if (confirm.ok) await execute_set_timedtask_allschemes();
                    else continue;

                } else if (action === 'B') {
                    console.log(chalk.bold.blue("************ SETTINGS TOEVOEGEN ************"));
                    console.log(chalk.yellow("=-=-= CONTROLEER DE SETTINGS IN DE CODE HARDCODED OF DEZE NU NOG VAN TOEPASSING ZIJN =-=-="));
                    const confirm = await inquirer.prompt([{ type: 'confirm', name: 'ok', message: 'Doorgaan?', default: false }]);
                    if (confirm.ok) await execute_add_settings();
                    else continue;

                } else if (action === 'C') {
                    console.log(chalk.bold.blue("************ SCHAKELTIJD AANPASSEN MODULES ************"));
                    console.log("Je gaat nu de modules aanpassen naar 60 seconden schakeltijd via de sendlist van een organisatie.");

                    let schema;
                    try {
                        schema = await chooseSchemaInteractive();
                    } catch (e) {
                        console.error(chalk.red('Kon geen organisatie kiezen: ' + e.message));
                        continue;
                    }

                    const dryRunAnswer = await inquirer.prompt([
                        {
                            type: 'list',
                            name: 'mode',
                            message: 'Kies uitvoermodus:',
                            choices: [
                                { name: 'Dry Run (Veilig - Alleen simuleren)', value: true },
                                { name: 'Live (LET OP: Wijzigingen worden doorgevoerd!)', value: false }
                            ],
                            pageSize: INQUIRER_PAGE_SIZE
                        }
                    ]);

                    console.log(`Je gaat nu de sendlist vullen voor organisatie: ${schema}.`);
                    if(dryRunAnswer.mode) console.log(chalk.magenta("MODUS: DRY RUN (Geen wijzigingen)"));
                    else console.log(chalk.red("MODUS: LIVE (Wijzigingen worden opgeslagen!)"));

                    const confirm = await inquirer.prompt([{ type: 'confirm', name: 'ok', message: 'Weet je het zeker?', default: false }]);

                    if (confirm.ok) {
                        await execute_change_schakelsettings_4850cm(schema, dryRunAnswer.mode);
                    } else {
                        continue;
                    }

                } else if (action === 'D') {
                    console.log(chalk.bold.blue("************ CHECK ENABLED TIMEDTASK STATUS ************"));
                    await execute_enabled_check();

                } else if (action === 'E') {
                    console.log(chalk.bold.blue("************ CHECK STATUS PER PARK ************"));
                    await get_status_per_park();

                } else if (action === 'F') {
                    console.log(chalk.bold.blue("************ UITDRAAI SCHAKELTIJDEN ************"));
                    await uitdraai_schakeltijden_4850();

                } else if (action === 'G') {
                    await fillSchemas();
                    console.log(chalk.cyan("************ ZOEK ORGANISATIE ************"));
                    const searchAnswer = await inquirer.prompt([{ type: 'input', name: 'term', message: 'Zoekterm (Regex ondersteund):' }]);
                    if (!searchAnswer.term) { console.log(chalk.red('Geen zoekterm opgegeven.')); continue; }
                    perform_search(searchAnswer.term);
                    console.log(chalk.cyan("************ KLAAR ************"));
                    // continue to action menu
                } else if (action === 'H') {
                    await execute_check_and_offer_convert_schakeltijden_all(true);
                }
            }
        }

    } catch (error) {
        console.error(chalk.red("Er is een fout opgetreden:"), error);
        process.exit(1);
    }
}
execute();
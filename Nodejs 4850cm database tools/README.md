# ICY4850CM Database Tools

Deze toolset is ontwikkeld voor het beheren en analyseren van ICY4850CM modules in de database.
Het biedt diverse functies voor configuratie, controle en rapportage.

## Vereisten
- Node.js moet geïnstalleerd zijn op het systeem.
- Een `.env` bestand met correcte databasegegevens.

## Gebruik
Start de applicatie via de terminal:
`node index.js`

Volg vervolgens de instructies op het scherm:
1. Selecteer de gewenste database (MySQL of MariaDB).
2. Kies een actie uit het menu.

> **LET OP:** Acties gemarkeerd met `(!)` voeren wijzigingen (INSERT/UPDATE) uit in de database.
> Deze opties vereisen extra bevestiging om onbedoelde wijzigingen te voorkomen.

## Beschikbare Opties

### A: (!) Timedtask toevoegen
Controleert per organisatie of de `ICY4850HARDWARECHECK` timedtask bestaat.
Indien afwezig, wordt deze automatisch toegevoegd met een willekeurige uitvoeringstijd tussen 03:00 en 06:00.
*Controleer vooraf of de hardcoded instellingen in het script nog actueel zijn.*

### B: (!) Settings toevoegen
Controleert per organisatie of de `ICY4850HARDWARECHECK` instellingen aanwezig zijn.
Indien afwezig, worden de standaardwaarden toegevoegd (standaard ingeschakeld).
*Controleer vooraf of de hardcoded instellingen in het script nog actueel zijn.*

### C: (!) Schakeltijd aanpassen (60 sec)
**WAARSCHUWING:** Dit is een risicovolle en tijdrovende actie!
Past de schakeltijd van alle modules binnen één specifieke organisatie aan naar 60 seconden ('3c').
- Leest de huidige configuratie, past de schakeltijd bit aan.
- Werkt `wantedconfig` en `unoccupiedconfig` bij in de database.
- Plaatst een commando in de `sendlist` (prioriteit 30).
*Vraag altijd eerst toestemming voordat je deze bulk-actie uitvoert.*

### D: Status Timedtask controleren
Geeft een overzicht per organisatie of de `ICY4850HARDWARECHECK` is ingeschakeld of uitgeschakeld.

### E: Rapportage Hardware Issues
Genereert een rapport van de huidige status in de `icy4850hardwareissue` tabel.
- Toont modules met status `UNRELIABLE`, `DEFECT` of `PREMATURE`.
- Negeert modules die niet meer voorkomen in de `slavedevice` tabel (reeds vervangen).
- Exporteert de resultaten naar een Excel-bestand.

### F: Rapportage Schakeltijden
Analyseert de schakeltijden van alle modules per organisatie.
- Rapporteert modules met een schakeltijd korter dan 60 seconden.
- Korte schakeltijden kunnen metingen beïnvloeden en worden als risico beschouwd.
- Exporteert de resultaten naar een Excel-bestand.

### G: Zoek Organisatie
Zoek snel naar een organisatienaam in de database met behulp van tekst of RegEx.

---
**DISCLAIMER:**
Verifieer altijd de data en instellingen voordat je schrijfacties uitvoert.
De auteur is niet verantwoordelijk voor onbedoelde datawijzigingen.
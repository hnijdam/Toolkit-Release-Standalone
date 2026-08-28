# Offset Behavior Notes

This file records the operational decisions found during live testing, so the
tool keeps behaving consistently later.

## Offset conventions

The app does not use one universal offset formula for every meter type.

Default convention:

```text
effective = (raw_value - offset) / meterdivider
offset = raw_value - desired_effective * meterdivider
```

Additive convention:

```text
effective = (raw_value + offset) / meterdivider
offset = desired_effective * meterdivider - raw_value
```

Confirmed additive meter types are configured in `offset_conventions.json`:

- `CAMPEREWS` / `campere_wall_socket`
- `CAMPEREMOD` / `campere_module`
- `PRMCAMPERE` / `prm_campere_meter`

There is also a narrowly scoped factor override for explicitly confirmed
device/slave pairs in the same config file. If the config file is missing or
cannot be read, the tool falls back to the built-in defaults.

## Manual input modes

The manual screen has two modes:

- `Zet meterstand op`: the entered value is the absolute target meter reading.
- `Tel op bij huidige stand`: the entered value is added to the current
  effective reading, and the sum is used as the target.

For example, if the current effective reading is `1.331` and the operator wants
to add `3000`, the target is `3001.331`, not `3000`.

## RCV after offset changes

Every real offset save or delete queues a `0x15` Request Counter Value command
in `sendlist`. After committing the DB change, the app waits for a newer
`pulsecounterlog` row for the same record scope.

Current wait behavior:

- timeout: 75 seconds
- polling interval: 2 seconds
- success is detected by a newer `pulsecounterlogid`, falling back to a newer
  timestamp if needed
- batch saves monitor all queued RCV responses in parallel within one shared
  timeout window

If the timeout is reached, the offset change is still committed, but the UI
shows a warning that the RCV response was not observed yet.

## Batch behavior

Batch preview validates every row before saving. Only rows with
`Klaar om op te slaan` are written. Blocked MID Campere meters, ambiguous rows,
missing rows, and invalid rows are skipped and logged.

Batch save uses the same offset and RCV flow as manual save. Before saving, the
preview can be exported as a dry-run Excel report with all target readings,
calculated offsets, status values, and skip reasons.

## Session audit

Every save/delete action and observed RCV result is stored in the current
Streamlit session audit. The UI exposes CSV and Excel downloads so the operator
can keep an evidence trail of what was changed during that session.

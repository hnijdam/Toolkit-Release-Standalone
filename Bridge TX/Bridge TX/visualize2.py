import os
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
import numpy as np


def visualize_bridge_csv_comlog(csv_filtered, csv_unfiltered, sort_by, output_dir=None):
    # Load CSV (no header)
    klantnaam = str(csv_filtered).split("_")[4]

    print(klantnaam)

    df1 = pd.read_csv(csv_filtered, header=None)
    df1.columns = ['id', 'bridge_id', 'message', 'comment', 'direction', 'timestamp', 'count', 'bridgetype', 'swversion', 'polling', 'pollfailure']
    df1['filtered'] = "yes"
    df1['restart'] = "no"
    df1["restart"] = np.where(
        df1["comment"].str.contains("5555 30 434f4e", na=False),
        "yes",
        "no"
        )

    df2 = pd.read_csv(csv_unfiltered, header=None)
    df2.columns = ['id', 'bridge_id', 'message', 'comment', 'direction', 'timestamp', 'count', 'bridgetype', 'swversion', 'polling', 'pollfailure']
    df2['filtered'] = "no"
    df2['restart'] = "no"



    # Merge both dataframes
    df = pd.concat([df1, df2], ignore_index=True)

    df.columns = ['id', 'bridge_id', 'message', 'comment', 'direction', 'timestamp', 'count', 'bridgetype', 'swversion', 'polling', 'pollfailure', "filtered", "restart"]



    # Convert timestamp column to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values(['bridge_id', 'timestamp'])

    # Gap threshold (15 minutes)
    threshold = timedelta(minutes=15)

    bridges = sorted(df['bridge_id'].unique(), reverse=True)

    # Build summary table for sorting
    summary_rows = []

    for bridge_id, bgroup in df.groupby("bridge_id"):

        bridgetype = bgroup["bridgetype"].iloc[0]
        swversion  = bgroup["swversion"].iloc[0]

        polling_val = bgroup["polling"].iloc[0]
        fail_val    = bgroup["pollfailure"].iloc[0]
        total = polling_val + fail_val
        poll_pct = (polling_val / total * 100) if total > 0 else 0
        fail_pct = (fail_val / total * 100) if total > 0 else 0

        restart_count   = (bgroup["restart"] == "yes").sum()
        filtered_count  = (bgroup["filtered"] == "yes").sum()
        unfiltered_count = (bgroup["filtered"] == "no").sum()

        summary_rows.append({
            "bridge_id": bridge_id,
            "restart": restart_count,
            "filtered": filtered_count,
            "unfiltered": unfiltered_count,
            "poll_pct": poll_pct,
            "fail_pct": fail_pct,
            "bridgetype": bridgetype,
            "swversion": swversion
        })

    summary_df = pd.DataFrame(summary_rows)

    # -----------------------------------------------------------
    # Sorting logic
    # -----------------------------------------------------------
    if sort_by not in summary_df.columns:
        print(f"[WARNING] sort_by '{sort_by}' is not valid. Using default.")
        sort_by = "bridge_id"

    summary_df = summary_df.sort_values(sort_by, ascending=False)
    bridges = summary_df["bridge_id"].tolist()   # sorted order!




    custom_labels = {}
    for _, row in summary_df.iterrows():
        bridge_id = row["bridge_id"]

        custom_labels[bridge_id] = (
            f"Bridge: {bridge_id}<br>"
            f"{row['bridgetype']} | SW {row['swversion']}<br>"
            f"Poll: {row['poll_pct']:.0f}% | Fail: {row['fail_pct']:.0f}%<br>"
            #f"Herstart berichten: {row['restart']}<br>"
            #f"abab berichten: {row['filtered']} <br>"
            #f"geen abab berichten: {row['unfiltered']}<br>"
            f"<span style='color:#000000'>Herstart berichten: {row['restart']}</span><br>"
            f"<span style='color:#D70338'>abab berichten: {row['filtered']}</span><br>"
            f"<span style='color:#1f77b4'>geen abab berichten: {row['unfiltered']}</span><br>"

        )




    num_bridges = len(bridges)

    fig = go.Figure()
    y_positions = {bridge_id: i for i, bridge_id in enumerate(bridges)}


    #colors = [
    #    "#1f77b4",
    #    "#D70338"
    #]

    all_shapes = []  # collect rectangles here





    for i, bridge_id in enumerate(bridges):
        group = df[df['bridge_id'] == bridge_id].sort_values('timestamp').copy()
        group['timediff'] = group['timestamp'].diff()
        y = y_positions[bridge_id]
        group["marker_size"] = np.where(
        group["restart"] == "yes",
        28,    # bigger marker for restart
        18     # normal marker size
        )
        # Determine color per row based on 'filtered' column
        group["color"] = np.where(
            group["restart"] == "yes", "#000000",
            np.where(group["filtered"] == "yes", "#D70338", "#1f77b4")
        )

        # Scatter points (using per-point color)
        fig.add_trace(go.Scatter(
            x=group['timestamp'],
            y=[y]*len(group),
            mode='markers',
            marker=dict(
                color=group["color"],
                size=group["marker_size"],   # <-- dynamic sizes per point
                symbol='line-ns-open'
            ),
            name=f"Bridge {bridge_id}",
            hovertext=[
                f"<b>Bridge {bridge_id}</b><br>"
                f"Timestamp: {t}<br>"
                #f"Filtered: {filt}<br>"
                f"Comment: {c4}"
                for t, filt, c4 in zip(group['timestamp'], group['filtered'], group['comment'])
            ],
            hoverinfo="text"
        ))



        # Record red gap rectangles (>15 min)
        for j in range(1, len(group)):
            if group['timediff'].iloc[j] > threshold:
                all_shapes.append(dict(
                    type="rect",
                    x0=group['timestamp'].iloc[j-1],
                    x1=group['timestamp'].iloc[j],
                    y0=y - 0.4,
                    y1=y + 0.4,
                    fillcolor="red",
                    opacity=0.7,
                    layer="below",
                    line_width=0,
                ))





    # Add all rectangles at once (MUCH faster)
    fig.update_layout(
        shapes=all_shapes,
        title=f"Communicatie per Bridge van {klantnaam.capitalize()}<br><sup>(Rood vierkantje = Gat > 15 Minuten) | Rode streep = berichten met 'ab abab' | Blauwe streep = bericht zonder 'ab abab | Zwarte streep = '434f4e' herstart bericht</sup>",
        xaxis_title="Timestamp",
        yaxis=dict(
            tickmode='array',
            tickvals=list(y_positions.values()),
            ticktext=[custom_labels[d] for d in bridges],
            showgrid=False,
        ),
        height=150 + num_bridges * 100,
        template="plotly_white",
        hovermode="closest",
        showlegend=False,
        margin=dict(t=50, b=5, l=0, r=5)
    )


#    fig.show()
    bestand_naam = "bridge_com_timeline.html"
    if output_dir:
        output_path = os.path.join(output_dir, f"{klantnaam} {bestand_naam}")
    else:
        output_path = f"{klantnaam} {bestand_naam}"
    fig.write_html(output_path, auto_open=True)
    print(f"Bestand: {output_path} opgeslagen")


#visualize_bridge_csv_comlog(r"C:\tmp\bridge_com_overzicht_alle_klanten_1440_min_filtered.csv",
#                            r"C:\tmp\bridge_com_overzicht_alle_klanten_1440_min_unfiltered.csv",
#                            "bridge_id"
#                     )


# Filter by options / arguments.
#            "bridge_id"
#            "restart"
#            "filtered"
#            "unfiltered"
#            "poll_pct"
#            "fail_pct"
#            "bridgetype"
#            "swversion"




from pathlib import Path
import argparse
import pandas as pd
import re


def main():
    parser = argparse.ArgumentParser(description='Combine per-db bridge health CSV reports into a single CSV and XLSX workbook')
    parser.add_argument('--dir', default='.', help='Directory containing per-db CSV reports (default: current dir)')
    parser.add_argument('--pattern', default='bridge_health_report_*.csv', help='Glob pattern for per-db CSVs')
    parser.add_argument('--out-prefix', default='bridge_health_report_combined', help='Output prefix for combined files')
    parser.add_argument('--keep-sources', action='store_true', help='Keep the original per-db CSV files (default: remove them after successful combine)')
    args = parser.parse_args()

    p = Path(args.dir)
    csvs = sorted(p.glob(args.pattern))
    if not csvs:
        print('No per-db CSV reports found.')
        raise SystemExit(1)

    combined_rows = []
    xlsx_path = p / (args.out_prefix + '.xlsx')
    csv_out = p / (args.out_prefix + '.csv')
    with pd.ExcelWriter(xlsx_path, engine='openpyxl') as ew:
        for f in csvs:
            try:
                # prefer semicolon-separated files with UTF-8 BOM, fallback to default CSV parsing
                try:
                    df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
                except Exception:
                    df = pd.read_csv(f)
            except Exception as e:
                print(f'Failed to read {f}: {e}')
                continue
            # sanitize sheet name
            sheet = re.sub(r"[\[\]\:\*\?/\\]", "_", f.stem)[:31]
            try:
                df.to_excel(ew, sheet_name=sheet, index=False)
            except Exception as e:
                print(f'Failed to write sheet {sheet}: {e}')
            df['source_db_report'] = f.name
            combined_rows.append(df)

    if combined_rows:
        combined = pd.concat(combined_rows, ignore_index=True)
        combined.to_csv(csv_out, index=False, sep=';', encoding='utf-8-sig')
        print(f'Wrote {csv_out} and {xlsx_path}')
        # remove source CSVs unless user requested to keep them
        if not args.keep_sources:
            removed = 0
            for f in csvs:
                try:
                    f.unlink()
                    removed += 1
                except Exception as e:
                    print(f'Failed to remove source file {f}: {e}')
            print(f'Removed {removed} source files')
    else:
        print('No data collected from per-db CSVs.')


if __name__ == '__main__':
    main()

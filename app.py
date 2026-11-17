import csv
import os
import sys
from datetime import datetime
from flask import Flask, render_template, request

sys.path.append(os.path.join(os.path.dirname(__file__), "main"))

import api_client
import data_processor
import chart_generator

app = Flask(__name__)


def load_stock_symbols():
    """Loads stock symbols from main/stocks.csv."""
    symbols = []
    for path in [os.path.join("main", "stocks.csv"), "stocks.csv"]:
        if os.path.exists(path):
            with open(path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and row[0].strip().upper() not in ("SYMBOL", "TICKER", ""):
                        symbols.append(row[0].strip().upper())
            break
    return symbols


@app.route("/", methods=["GET", "POST"])
def index():
    symbols = load_stock_symbols()
    errors = []
    chart_svg = None
    form_data = {
        "symbol": "",
        "chart_type": "",
        "time_series": "",
        "start_date": "",
        "end_date": "",
    }

    if request.method == "POST":
        symbol = request.form.get("symbol", "").strip().upper()
        chart_type = request.form.get("chart_type", "").strip().lower()
        time_series = request.form.get("time_series", "").strip()
        start_date_str = request.form.get("start_date", "").strip()
        end_date_str = request.form.get("end_date", "").strip()

        form_data = {
            "symbol": symbol,
            "chart_type": chart_type,
            "time_series": time_series,
            "start_date": start_date_str,
            "end_date": end_date_str,
        }

        # 1. Symbol input error checking
        if not symbol or symbol not in symbols:
            errors.append("Please select a valid stock symbol.")

        # 2. Chart Type input error checking
        if chart_type not in ("bar", "line"):
            errors.append("Please select a valid chart type (Bar or Line).")

        # 3. Time Series input error checking
        valid_series = (
            "TIME_SERIES_INTRADAY",
            "TIME_SERIES_DAILY",
            "TIME_SERIES_WEEKLY",
            "TIME_SERIES_MONTHLY",
        )
        if time_series not in valid_series:
            errors.append("Please select a valid time series function.")

        # 4. Start Date & End Date error checking
        start_dt = None
        end_dt = None
        if not start_date_str:
            errors.append("Start date is required.")
        else:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append("Invalid start date format.")

        if not end_date_str:
            errors.append("End date is required.")
        else:
            try:
                end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append("Invalid end date format.")

        # 5. End Date after Start Date error checking
        if start_dt and end_dt and end_dt <= start_dt:
            errors.append("End date must be after the start date.")

        if not errors:
            try:
                raw = api_client.fetch_stock_data(symbol, time_series)
                df = data_processor.build_dataframe(raw)
                df = data_processor.filter_by_date(df, start_dt, end_dt)

                # Prevent webbrowser.open from crashing inside headless Docker
                import webbrowser
                webbrowser.open = lambda *args, **kwargs: True

                chart_generator.create_chart(df, symbol, chart_type, time_series, start_dt, end_dt)

                for svg_path in ["chart.svg", os.path.join("main", "chart.svg")]:
                    if os.path.exists(svg_path):
                        with open(svg_path, "r", encoding="utf-8") as svg_file:
                            chart_svg = svg_file.read()
                        break

                if not chart_svg:
                    errors.append("Chart was generated, but chart.svg could not be read.")
            except Exception as err:
                errors.append(f"Error: {err}")

    return render_template(
        "index.html",
        symbols=symbols,
        errors=errors,
        chart_svg=chart_svg,
        form_data=form_data,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

"""Plotly chart builders. Every chart states whether it shows forecast or observed data, and its units."""

import pandas as pd
import plotly.graph_objects as go

RAIN_COLOR = "#1d6fa5"
TEMP_MAX_COLOR = "#c2410c"
TEMP_MIN_COLOR = "#0f766e"
GRID_COLOR = "#e6e1d3"
TEXT_COLOR = "#1c2b22"


def _base_layout(fig: go.Figure, title: str, height: int, date_axis: bool = True) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=TEXT_COLOR), x=0, xanchor="left"),
        height=height,
        margin=dict(l=16, r=16, t=56, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=14, color=TEXT_COLOR),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=13)),
        hovermode="x unified",
        hoverlabel=dict(font_size=14),
    )
    if date_axis:
        fig.update_xaxes(showgrid=False, tickformat="%d %b", tickfont=dict(size=13), title_text="Date")
    fig.update_yaxes(gridcolor=GRID_COLOR, tickfont=dict(size=13))
    return fig


def rainfall_forecast_chart(daily: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        x=daily["date"],
        y=daily["rain_mm"],
        name="Forecast rain (mm)",
        marker_color=RAIN_COLOR,
        hovertemplate="%{y:.1f} mm<extra>Forecast rain</extra>",
    )
    fig.update_yaxes(title_text="Rainfall (mm)", rangemode="tozero")
    return _base_layout(fig, "Rainfall forecast, next 7 days", 340)


def temperature_forecast_chart(daily: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(
        x=daily["date"],
        y=daily["tmax"],
        name="Forecast maximum (°C)",
        mode="lines+markers",
        line=dict(color=TEMP_MAX_COLOR, width=3),
        marker=dict(size=9),
        hovertemplate="%{y:.1f} °C<extra>Forecast max</extra>",
    )
    fig.add_scatter(
        x=daily["date"],
        y=daily["tmin"],
        name="Forecast minimum (°C)",
        mode="lines+markers",
        line=dict(color=TEMP_MIN_COLOR, width=3),
        marker=dict(size=9),
        hovertemplate="%{y:.1f} °C<extra>Forecast min</extra>",
    )
    fig.update_yaxes(title_text="Temperature (°C)")
    return _base_layout(fig, "Minimum and maximum temperature, next 7 days", 340)


def history_chart(history: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        x=history["date"],
        y=history["rain_mm"],
        name="Observed rain (mm)",
        marker_color=RAIN_COLOR,
        hovertemplate="%{y:.1f} mm<extra>Observed rain</extra>",
    )
    fig.add_scatter(
        x=history["date"],
        y=history["tmax"],
        name="Observed max temp (°C)",
        mode="lines",
        yaxis="y2",
        line=dict(color=TEMP_MAX_COLOR, width=2.5),
        hovertemplate="%{y:.1f} °C<extra>Observed max</extra>",
    )
    fig.update_layout(
        yaxis=dict(title_text="Rainfall (mm)", rangemode="tozero"),
        yaxis2=dict(title_text="Temperature (°C)", overlaying="y", side="right", showgrid=False),
    )
    return _base_layout(fig, "Observed history, last 30 days (measured, not a forecast)", 360)


def mandi_price_chart(rows: pd.DataFrame) -> go.Figure:
    top = rows.sort_values("modal_price", ascending=False).head(12)
    fig = go.Figure()
    fig.add_bar(
        x=top["market"],
        y=top["modal_price"],
        marker_color="#14532d",
        name="Modal price (₹/quintal)",
        hovertemplate="₹%{y:,.0f} per quintal<extra>%{x}</extra>",
    )
    fig.update_yaxes(title_text="Modal price (₹ per quintal)", rangemode="tozero")
    fig.update_xaxes(title_text="Market", showgrid=False)
    fig.update_layout(hovermode="closest")
    return _base_layout(fig, "Modal price by market (latest reported date)", 380, date_axis=False)

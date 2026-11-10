"""Componentes visuales: tema minimalista corporativo y piezas reutilizables."""
from __future__ import annotations

import html

import streamlit as st

CSS = """
:root { --cz-navy:#0B2545; --cz-accent:#1F6FEB; --cz-muted:#5B6B7F; --cz-line:#E3E8EF; }
.block-container { padding-top: 2rem; max-width: 1180px; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
h1, h2, h3 { color: var(--cz-navy); letter-spacing: -0.01em; }
.cz-brand { font-weight: 700; color: var(--cz-navy); font-size: 1.35rem; margin-bottom: .25rem; }
.cz-brand span { color: var(--cz-accent); }
.cz-kpi { border: 1px solid var(--cz-line); border-radius: 12px; padding: 14px 16px; background: #fff; }
.cz-kpi .lbl { font-size: .74rem; color: var(--cz-muted); text-transform: uppercase; letter-spacing: .06em; }
.cz-kpi .val { font-size: 1.3rem; font-weight: 650; color: var(--cz-navy); margin-top: 2px; }
div.stButton > button[kind="primary"] { background: var(--cz-navy); border-color: var(--cz-navy); }
div.stButton > button[kind="primary"]:hover { background: var(--cz-accent); border-color: var(--cz-accent); }
.cz-footer { color: var(--cz-muted); font-size: .8rem; text-align: center; margin-top: 2.5rem; }
"""


def apply_theme() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def brand() -> None:
    st.markdown('<div class="cz-brand">CENSUS <span>Avalúos</span></div>', unsafe_allow_html=True)


def step_header(n: int, total: int, title: str) -> None:
    st.caption(f"PASO {n} DE {total}")
    st.subheader(title)
    st.progress(n / total)


def kpi(label: str, value: str) -> None:
    st.markdown(
        f'<div class="cz-kpi"><div class="lbl">{html.escape(label)}</div>'
        f'<div class="val">{html.escape(value)}</div></div>',
        unsafe_allow_html=True,
    )


def fmt_cop(valor) -> str:
    return "$ " + f"{float(valor):,.0f}".replace(",", ".")


def footer() -> None:
    st.markdown(
        '<div class="cz-footer">Census Avalúos · Desarrollado por Adaptiva.com.co</div>',
        unsafe_allow_html=True,
    )

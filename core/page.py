"""Page setup helpers."""

from __future__ import annotations

import streamlit as st


def init_page(*, title: str, icon: str) -> None:
    """Set up a Streamlit page with common chrome tweaks."""
    st.set_page_config(page_title=title, page_icon=icon)
    st.title(f"{icon} {title}")
    st.markdown(
        """
        <style>
        [data-testid="stToolbarActions"] {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )


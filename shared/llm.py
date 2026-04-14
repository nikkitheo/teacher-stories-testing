"""Shared LLM adapter helpers."""

from __future__ import annotations

import os

import streamlit as st
from langchain_openai import ChatOpenAI


@st.cache_resource
def get_chat_model(model_name: str, temperature: float = 0.3) -> ChatOpenAI:
    """Create a cached ChatOpenAI client."""
    return ChatOpenAI(
        temperature=temperature,
        model=model_name,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )


def ensure_openai_key() -> None:
    """Ensure an OpenAI key is available before LLM steps run."""
    if "OPENAI_API_KEY" in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    elif not os.environ.get("OPENAI_API_KEY"):
        api_key = st.sidebar.text_input("OpenAI API Key", type="password")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

    if not os.environ.get("OPENAI_API_KEY"):
        st.info("Enter an OpenAI API Key to continue")
        st.stop()

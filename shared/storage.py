"""Shared storage helpers and adapters."""

from __future__ import annotations

import boto3
import streamlit as st


logger = st.logger.get_logger("v2_storage")


@st.cache_resource(show_spinner=False)
def get_table(table_name: str | None, *, required: bool = False):
    """Get a DynamoDB table if available."""
    if not table_name:
        if required:
            raise RuntimeError("No table name provided for a required table")
        return None

    try:
        resource = boto3.Session().resource("dynamodb")
        existing = [table.name for table in resource.tables.all()]
        if table_name in existing:
            return resource.Table(table_name)
    except Exception as exc:  # pragma: no cover
        if required:
            raise
        logger.warning("Failed to access DynamoDB: %s", exc)
        return None

    if required:
        raise RuntimeError(f"Required table '{table_name}' not found")
    return None


def save_item(table, item: dict) -> bool:
    """Save an item to DynamoDB if the table exists."""
    if table is None:
        return False
    try:
        table.put_item(Item=item)
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to save item: %s", exc)
        return False


def fetch_latest_by_participant(table, participant_id: str, *, scenario_key: str = "final_scenario") -> str | None:
    """Fetch the most recent saved scenario for a participant."""
    if table is None or not participant_id:
        return None
    try:
        result = table.scan(
            FilterExpression="participant_id = :pid",
            ExpressionAttributeValues={":pid": participant_id},
            ProjectionExpression=f"participant_id, {scenario_key}, completion_time",
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to fetch previous scenario: %s", exc)
        return None

    items = result.get("Items", [])
    if not items:
        return None

    latest = sorted(items, key=lambda item: item.get("completion_time", ""), reverse=True)[0]
    return latest.get(scenario_key)

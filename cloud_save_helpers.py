import hashlib

from datetime import datetime, timezone

import streamlit as st

from supabase import create_client

TABLE_NAME = "saved_scenarios"

def get_supabase_client():
    """
    Creates and returns a Supabase client using Streamlit secrets.
    """

    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]

    return create_client(supabase_url, supabase_key)


def hash_access_code(access_code):
    """
    Hashes the access code so the raw code is not stored in the database.
    """

    cleaned_code = str(access_code).strip()

    if cleaned_code == "":
        raise ValueError("Please enter an access code.")

    salt = st.secrets["cloud_save"]["access_code_salt"]
    salted_code = f"{salt}:{cleaned_code}"

    return hashlib.sha256(salted_code.encode("utf-8")).hexdigest()


def save_scenario_to_cloud(scenario_name, access_code, scenario_json):
    """
    Saves a scenario to Supabase.
    """

    if str(scenario_name).strip() == "":
        raise ValueError("Please enter a scenario name.")

    access_code_hash = hash_access_code(access_code)

    row = {
        "scenario_name": str(scenario_name).strip(),
        "access_code_hash": access_code_hash,
        "scenario_json": scenario_json,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    supabase = get_supabase_client()

    response = (
        supabase
        .table(TABLE_NAME)
        .insert(row)
        .execute()
    )

    return response.data


def list_scenarios_for_access_code(access_code):
    """
    Lists saved scenarios matching an access code.
    """

    access_code_hash = hash_access_code(access_code)

    supabase = get_supabase_client()

    response = (
        supabase
        .table(TABLE_NAME)
        .select("id, scenario_name, created_at, updated_at")
        .eq("access_code_hash", access_code_hash)
        .order("updated_at", desc=True)
        .execute()
    )

    return response.data


def load_scenario_from_cloud(scenario_id, access_code):
    """
    Loads one saved scenario by id and access code.
    """

    access_code_hash = hash_access_code(access_code)

    supabase = get_supabase_client()

    response = (
        supabase
        .table(TABLE_NAME)
        .select("scenario_json")
        .eq("id", scenario_id)
        .eq("access_code_hash", access_code_hash)
        .single()
        .execute()
    )

    return response.data["scenario_json"]


def delete_scenario_from_cloud(scenario_id, access_code):
    """
    Deletes one saved scenario by id and access code.
    """

    access_code_hash = hash_access_code(access_code)

    supabase = get_supabase_client()

    response = (
        supabase
        .table(TABLE_NAME)
        .delete()
        .eq("id", scenario_id)
        .eq("access_code_hash", access_code_hash)
        .execute()
    )

    return response.data
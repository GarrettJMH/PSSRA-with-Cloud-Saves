import json
import re
from datetime import datetime


REQUIRED_SCENARIO_FIELDS = ["projects", "workers", "q_matrix", "settings"]


def make_safe_filename(name):
    """
    Creates a safe filename from the scenario name.
    """

    cleaned_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).strip())
    cleaned_name = cleaned_name.strip("_")

    if cleaned_name == "":
        cleaned_name = "PSSRA_Scenario"

    return f"{cleaned_name}_Save.json"

def build_scenario_dictionary(
        scenario_name,
        projects,
        workers,
        q_matrix,
        settings
):
    """
    Builds a scenario dictionary that can be saved as JSON or stored in a database.
    """

    if str(scenario_name).strip() == "":
        scenario_name = "Untitled Scenario"

    scenario_data = {
        "app_name": "PSSRA Optimizer",
        "save_file_version": "1.0",
        "scenario_name": scenario_name,
        "saved_at": datetime.now().isoformat(timespace="seconds"),
        "projects": projects,
        "workers": workers,
        "q_matrix": q_matrix,
        "settings": settings
    }

    return scenario_data

def build_scenario_save_data(
    scenario_name,
    projects,
    workers,
    q_matrix,
    settings
):
    """
    Builds a downloadable JSON scenario save file.
    """

    scenario_data = build_scenario_dictionary(
        scenario_name=scenario_name,
        projects=projects,
        workers=workers,
        q_matrix=q_matrix,
        settings=settings
    )

    return json.dumps(
        scenario_data,
        indent=2,
        default=str
    ).encode("utf-8")


def read_uploaded_scenario_file(uploaded_file):
    """
    Reads and validates an uploaded JSON scenario file.
    Returns the loaded scenario dictionary.
    Raises ValueError if the file is invalid.
    """

    if uploaded_file is None:
        raise ValueError("Please upload a scenario file first.")

    try:
        file_text = uploaded_file.getvalue().decode("utf-8")
        scenario_data = json.loads(file_text)
    except Exception:
        raise ValueError("Could not read this file. Please upload a valid scenario JSON file.")

    if not isinstance(scenario_data, dict):
        raise ValueError("This file is not a valid scenario save file.")

    missing_fields = [
        field for field in REQUIRED_SCENARIO_FIELDS
        if field not in scenario_data
    ]

    if len(missing_fields) > 0:
        raise ValueError(
            f"This scenario file is missing required fields: {', '.join(missing_fields)}."
        )

    if not isinstance(scenario_data.get("projects"), list):
        raise ValueError("This scenario file has an invalid projects section.")

    if not isinstance(scenario_data.get("workers"), list):
        raise ValueError("This scenario file has an invalid workers section.")

    if not isinstance(scenario_data.get("q_matrix"), list):
        raise ValueError("This scenario file has an invalid Q matrix section.")

    if not isinstance(scenario_data.get("settings"), dict):
        raise ValueError("This scenario file has an invalid settings section.")

    return scenario_data
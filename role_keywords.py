import pandas as pd


ROLE_LIBRARY_FILE = "role_library.csv"


def split_items(value):
    """
    Converts comma-separated or semicolon-separated text into a clean list.
    Handles blank cells safely.
    """

    if isinstance(value, list):
        return value

    if value is None:
        return []

    if pd.isna(value):
        return []

    # Allows either commas or semicolons in the CSV.
    text = str(value).replace(";", ",")

    return [
        item.strip()
        for item in text.split(",")
        if item.strip() != ""
    ]


def load_role_library(file_path=ROLE_LIBRARY_FILE):
    """
    Loads the role library from a CSV file.

    Required columns:
    - Role
    - Description
    - Keywords
    - Related roles

    Optional enhanced columns:
    - Responsibilities
    - Positive keywords
    - Negative keywords
    """

    role_df = pd.read_csv(file_path)

    required_columns = ["Role", "Description", "Keywords", "Related roles"]

    for column in required_columns:
        if column not in role_df.columns:
            raise ValueError(f"Missing required role-library column: {column}")

    roles = []
    role_descriptions = {}
    role_keywords = {}
    related_skills = {}

    role_responsibilities = {}
    positive_keywords = {}
    negative_keywords = {}

    for _, row in role_df.iterrows():
        role = str(row["Role"]).strip()

        if role == "":
            continue

        roles.append(role)

        role_descriptions[role] = str(row.get("Description", "")).strip()
        role_keywords[role] = split_items(row.get("Keywords", ""))
        related_skills[role] = split_items(row.get("Related roles", ""))

        role_responsibilities[role] = split_items(row.get("Responsibilities", ""))
        positive_keywords[role] = split_items(row.get("Positive keywords", ""))
        negative_keywords[role] = split_items(row.get("Negative keywords", ""))

    return (
        roles,
        role_descriptions,
        role_keywords,
        related_skills,
        role_responsibilities,
        positive_keywords,
        negative_keywords
    )
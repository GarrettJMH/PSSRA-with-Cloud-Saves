# The main app can use this file when AI generation is enabled and an API key is available.

import json
import re
import os

from google import genai
from google.genai import types


def get_gemini_api_key():
    """
    Gets the Gemini API key from the environment.

    Locally, this can come from your shell/environment variable.
    On Streamlit Community Cloud, this can come from Streamlit Secrets
    if the secret is added as:
    GEMINI_API_KEY = "your-key-here"
    """

    return os.getenv("GEMINI_API_KEY")


def gemini_api_key_available():
    """
    Checks whether a Gemini API key is available.
    Used by the Streamlit app to decide whether to show the Gemini button.
    """

    api_key = get_gemini_api_key()
    return api_key is not None and api_key.strip() != ""


def split_items(value):
    """
    Converts comma-separated text into a clean list.
    Also handles values that are already lists.
    """

    if isinstance(value, list):
        return value

    if value is None:
        return []

    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip() != ""
    ]


def get_used_roles(projects):
    """
    Gets only the roles that are actually used by the current projects.
    This reduces the amount of role-library information sent to Gemini.
    """

    used_roles = set()

    for project in projects:
        project_roles = split_items(project.get("Roles", ""))

        for role in project_roles:
            used_roles.add(role)

    return list(used_roles)


def clamp_q_value(value):
    """
    Ensures the Q value is numeric and between 0.00 and 1.00.
    """

    try:
        q_value = float(value)
    except (TypeError, ValueError):
        q_value = 0.0

    return round(max(0.0, min(q_value, 1.0)), 2)


def simplify_workers_for_gemini(workers):
    """
    Keeps only worker fields needed for Gemini Q generation.
    """

    simplified_workers = []

    for worker in workers:
        simplified_workers.append({
            "Worker name": worker.get("Worker name", ""),
            "Profile": worker.get("Profile", ""),
            "Skills": worker.get("Skills", "")
        })

    return simplified_workers


def simplify_projects_for_gemini(projects):
    """
    Keeps only project fields needed for Gemini Q generation.
    """

    simplified_projects = []

    for project in projects:
        simplified_projects.append({
            "Project name": project.get("Project name", ""),
            "Project context": project.get("Project context", ""),
            "Roles": project.get("Roles", "")
        })

    return simplified_projects


# Gemini responses are cleaned and validated because model output may include extra formatting.
def extract_json_array(text):
    """
    Attempts to extract a JSON array from Gemini's response.

    Handles:
    - raw JSON arrays
    - JSON inside markdown code fences
    - JSON objects containing a list
    - extra text around the JSON
    """

    if text is None:
        raise ValueError("Gemini response text was empty.")

    cleaned_text = text.strip()

    # Remove markdown code fences if Gemini returns ```json ... ```
    cleaned_text = cleaned_text.replace("```json", "")
    cleaned_text = cleaned_text.replace("```", "")
    cleaned_text = cleaned_text.strip()

    try:
        parsed = json.loads(cleaned_text)

        if isinstance(parsed, list):
            return parsed

        # If Gemini returned an object with a common list key.
        if isinstance(parsed, dict):
            for key in ["q_matrix", "Q Matrix", "rows", "data", "results"]:
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]

            # If single row object, wrap it in a list.
            if all(k in parsed for k in ["Worker", "Project", "Role", "Q Value"]):
                return [parsed]

    except json.JSONDecodeError:
        pass

    # Try to extract the first JSON array from surrounding text.
    match = re.search(r"\[.*\]", cleaned_text, re.DOTALL)

    if match:
        return json.loads(match.group(0))

    raise ValueError("Could not parse Gemini response as JSON.")


def build_role_library_text(roles, role_descriptions, keywords, related_skills):
    """
    Converts the role library into text that can be included in the Gemini prompt.
    """

    role_lines = []

    for role in roles:
        role_lines.append({
            "Role": role,
            "Description": role_descriptions.get(role, ""),
            "Keywords": keywords.get(role, []),
            "Related roles": related_skills.get(role, [])
        })

    return json.dumps(role_lines, indent=2)


# Prompt construction.
def build_q_generation_prompt(workers, projects, roles, role_descriptions, keywords, related_skills):
    """
    Builds the prompt sent to Gemini for Q-matrix generation.
    Sends only the roles used by the current projects to reduce API usage.
    """

    used_roles = get_used_roles(projects)

    role_library_text = build_role_library_text(
        used_roles,
        role_descriptions,
        keywords,
        related_skills
    )

    prompt = f"""
You are generating a Q matrix for a project-selection and role-assignment optimization model.

The Q matrix structure is:
Q[worker][project][role]

Return ONLY a valid JSON array. Do not include markdown, code fences, explanations, or extra text.

Each object must have exactly these keys:
- Worker
- Project
- Role
- Q Value

Q Value must be a number from 0.00 to 1.00:
0.00 = not suitable
0.30 = minimally suitable
0.50 = moderately suitable
0.80 = highly suitable
1.00 = excellent fit

Suitability must be project-specific. The same worker-role pair may receive different Q values for different projects if the project context differs.
Be conservative. Give high scores only when the worker profile or skills clearly support the project role.

Example JSON format:
[
  {{
    "Worker": "Bob",
    "Project": "Coding",
    "Role": "Developer",
    "Q Value": 0.75
  }}
]

Workers:
{json.dumps(simplify_workers_for_gemini(workers), indent=2)}

Projects:
{json.dumps(simplify_projects_for_gemini(projects), indent=2)}

Role library:
{role_library_text}
"""

    return prompt


def validate_gemini_q_rows(gemini_rows, workers, projects):
    """
    Validates Gemini-generated Q rows.

    This checks:
    - worker names exist
    - project names exist
    - roles are required by the project
    - Q values are numeric and between 0 and 1
    """

    valid_worker_names = {
        str(worker.get("Worker name", "")).strip()
        for worker in workers
        if str(worker.get("Worker name", "")).strip() != ""
    }

    project_roles = {}

    for project in projects:
        project_name = str(project.get("Project name", "")).strip()

        if project_name != "":
            project_roles[project_name] = split_items(project.get("Roles", ""))

    cleaned_rows = []

    for row in gemini_rows:
        worker = str(row.get("Worker", "")).strip()
        project = str(row.get("Project", "")).strip()
        role = str(row.get("Role", "")).strip()

        if worker not in valid_worker_names:
            continue

        if project not in project_roles:
            continue

        if role not in project_roles[project]:
            continue

        cleaned_rows.append({
            "Worker": worker,
            "Project": project,
            "Role": role,
            "Q Value": clamp_q_value(row.get("Q Value", 0.0)),
        })

    return cleaned_rows


def fill_missing_q_rows(q_rows, workers, projects):
    """
    Ensures every worker-project-role combination exists.

    If Gemini misses any rows, this fills them with a conservative default Q value.
    """

    existing_keys = {
        (row["Worker"], row["Project"], row["Role"])
        for row in q_rows
    }

    completed_rows = list(q_rows)

    for worker in workers:
        worker_name = str(worker.get("Worker name", "")).strip()

        if worker_name == "":
            continue

        for project in projects:
            project_name = str(project.get("Project name", "")).strip()
            project_roles = split_items(project.get("Roles", ""))

            if project_name == "":
                continue

            for role in project_roles:
                key = (worker_name, project_name, role)

                if key not in existing_keys:
                    completed_rows.append({
                        "Worker": worker_name,
                        "Project": project_name,
                        "Role": role,
                        "Q Value": 0.20,
                    })

    return completed_rows


# Main Gemini workflow.
def generate_q_matrix_with_gemini(
    workers,
    projects,
    roles,
    role_descriptions,
    keywords,
    related_skills,
    model_name="gemini-2.5-flash"
):
    """
    Generates a Q matrix using Gemini.

    This function:
    1. Checks that a Gemini API key exists.
    2. Creates the Gemini client only when Gemini is actually used.
    3. Builds a prompt from workers, projects, and role library data.
    4. Sends the prompt to Gemini.
    5. Parses the JSON response.
    6. Validates the returned Q rows.
    7. Fills in any missing worker-project-role rows.
    """

    api_key = get_gemini_api_key()

    if not api_key:
        raise ValueError("Gemini API key not found.")

    # The client is created inside this function, not globally. This lets the app run normally when no API key exists.
    client = genai.Client(api_key=api_key)

    prompt = build_q_generation_prompt(
        workers,
        projects,
        roles,
        role_descriptions,
        keywords,
        related_skills
    )

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
            max_output_tokens=4000
        )
    )

    raw_response = response.text

    # Optional debugging output.
    print("RAW GEMINI RESPONSE:")
    print(raw_response)

    try:
        with open("gemini_raw_response.txt", "w", encoding="utf-8") as file:
            file.write(str(raw_response))
    except Exception:
        # Avoid crashing the app if the cloud environment cannot write the debug file.
        pass

    gemini_rows = extract_json_array(raw_response)

    cleaned_rows = validate_gemini_q_rows(
        gemini_rows,
        workers,
        projects
    )

    completed_rows = fill_missing_q_rows(
        cleaned_rows,
        workers,
        projects
    )

    return completed_rows

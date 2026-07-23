import re

import pandas as pd

from role_keywords import load_role_library


(
    roles,
    Role_Descriptions,
    Keywords,
    Related_Skills,
    Responsibilities,
    Positive_Keywords,
    Negative_Keywords
) = load_role_library()


def split_items(value):
    """
    Converts comma-separated text into a clean list.
    Handles lists, None, blank values, and NaN spreadsheet/editor values.
    """

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if not pd.isna(item) and str(item).strip() != ""
        ]

    if value is None:
        return []

    if pd.isna(value):
        return []

    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip() != ""
    ]


def count_matches(terms, profile_lower):
    """
    Counts which terms appear in the worker profile.
    Returns the matched terms.
    """

    matches = []

    for term in terms:
        term_clean = str(term).strip()
        term_lower = term_clean.lower()

        if term_lower != "" and term_lower in profile_lower:
            matches.append(term_clean)

    return matches

PROJECT_CONTEXT_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "will",
    "need", "needs", "using", "used", "user", "users", "project", "role",
    "roles", "task", "tasks", "work", "team", "create", "develop",
    "build", "support", "system", "department"
}

SHORT_ALLOWED_TERMS = {"ai", "ux", "ui", "qa"}


def extract_project_terms(value):
    """
    Extracts useful keyword-like terms from project context text.
    This allows a normal project description to be used for project-specific Q scoring.
    """

    if value is None:
        return []

    text = str(value).lower()
    raw_terms = re.findall(r"[a-zA-Z0-9]+", text)

    terms = []

    for term in raw_terms:
        term = term.strip().lower()

        if term == "":
            continue

        if term in PROJECT_CONTEXT_STOPWORDS:
            continue

        if len(term) >= 3 or term in SHORT_ALLOWED_TERMS:
            terms.append(term)

    return sorted(set(terms))


def count_context_matches(project_terms, worker_text_lower):
    """
    Counts project-context terms that appear in the worker's profile or skills.
    Uses word boundaries so short terms do not match inside unrelated words.
    """

    matches = []

    for term in project_terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"

        if re.search(pattern, worker_text_lower):
            matches.append(term)

    return matches

def generate_q(worker_skills, worker_profile, role, project_name="", project_context=""):    
    """
    Generates one Q value for a worker-role combination.

    Scoring logic:
    Base score: 0.20
    Exact role skill match: +0.45
    Related role match: +0.15
    Positive keyword matches: +0.05 each, capped at +0.20
    Responsibility matches: +0.05 each, capped at +0.15
    General keyword matches: +0.03 each, capped at +0.09
    Negative keyword matches: -0.10 each, capped at -0.20
    Final score is capped between 0.00 and 1.00.
    """

    q_value = 0.20
    reasons = []

    worker_skills = split_items(worker_skills)
    worker_skills_lower = [
        skill.lower().strip()
        for skill in worker_skills
    ]

    role_lower = role.lower().strip()
    profile_lower = str(worker_profile).lower()
    worker_text_lower = (str(worker_profile) + " " + str(worker_skills)).lower()

    # Exact role match.
    if role_lower in worker_skills_lower:
        q_value += 0.45
        reasons.append(f"Exact skill match: {role}")

    # Related role match.
    related_skills = Related_Skills.get(role, [])

    for related_skill in related_skills:
        if related_skill.lower().strip() in worker_skills_lower:
            q_value += 0.15
            reasons.append(f"Related skill match: {related_skill}")
            break

    # Positive keyword matches.
    positive_matches = count_matches(
        Positive_Keywords.get(role, []),
        profile_lower
    )

    positive_bonus = min(len(positive_matches) * 0.05, 0.20)
    q_value += positive_bonus

    if positive_matches:
        reasons.append(
            "Positive matches: " + ", ".join(positive_matches[:5])
        )

    # Responsibility matches.
    responsibility_matches = count_matches(
        Responsibilities.get(role, []),
        profile_lower
    )

    responsibility_bonus = min(len(responsibility_matches) * 0.05, 0.15)
    q_value += responsibility_bonus

    if responsibility_matches:
        reasons.append(
            "Responsibility matches: " + ", ".join(responsibility_matches[:5])
        )

    # General keyword matches.
    keyword_matches = count_matches(
        Keywords.get(role, []),
        profile_lower
    )

    keyword_bonus = min(len(keyword_matches) * 0.03, 0.09)
    q_value += keyword_bonus

    if keyword_matches:
        reasons.append(
            "General keyword matches: " + ", ".join(keyword_matches[:5])
        )

    # Negative keyword matches.
    negative_matches = count_matches(
        Negative_Keywords.get(role, []),
        profile_lower
    )

    # Project-context matches.
    project_terms = extract_project_terms(
        str(project_name) + " " + str(project_context)
    )

    project_context_matches = count_context_matches(
        project_terms,
        worker_text_lower
    )

    # Matches between project context and worker profile/skills are treated as positive evidence.
    project_context_bonus = min(len(project_context_matches) * 0.05, 0.20)
    q_value += project_context_bonus

    if project_context_matches:
        reasons.append(
            "Project-context matches: " + ", ".join(project_context_matches[:5])
        )

    negative_penalty = min(len(negative_matches) * 0.10, 0.20)
    q_value -= negative_penalty

    if negative_matches:
        reasons.append(
            "Negative matches: " + ", ".join(negative_matches[:5])
        )

    # Keep final Q value between 0.00 and 1.00.
    q_value = round(max(0.00, min(q_value, 1.00)), 2)

    if not reasons:
        reasons.append("Base score only; no strong role evidence found.")

    return q_value, "; ".join(reasons)


def generate_q_matrix(workers, projects):
    """
    Generates the full Q matrix in row/table format.
    Each row represents one worker-project-role combination.
    """

    Q = []

    for worker in workers:
        worker_name = worker.get("Worker name", "")
        worker_profile = worker.get("Profile", "")
        worker_skills = worker.get("Skills", "")

        if str(worker_name).strip() == "":
            continue

        for project in projects:
            project_name = project.get("Project name", "")

            if project_name is None or pd.isna(project_name) or str(project_name).strip() == "":
                continue

            project_roles = split_items(project.get("Roles", ""))

            if len(project_roles) == 0:
                continue

            if str(project_name).strip() == "":
                continue

            for role in project_roles:
                q_value, reason = generate_q(
                    worker_skills=worker_skills,
                    worker_profile=worker_profile,
                    role=role,
                    project_name=project_name,
                    project_context=project.get("Project context", "")
                )

                Q.append({
                    "Worker": worker_name,
                    "Project": project_name,
                    "Role": role,
                    "Q Value": q_value,
                    "Reason": reason
                })

    return Q
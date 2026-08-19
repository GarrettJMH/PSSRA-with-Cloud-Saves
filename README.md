# Project Selection, Scheduling, and Role Assignment Prototype

This is a Streamlit prototype for project selection, scheduling, and role assignment. The prototype uses a PuLP optimization model to help users select projects, assign workers to required project roles, and build a weekly schedule while considering deadlines, worker availability, weekly capacity, project dependencies, project conflicts, and suitability scores.

## Purpose

Small departments often have many competing projects but limited staff. This prototype supports decision-making by combining:

- Project selection
- Project scheduling
- Worker-role assignment
- Worker suitability scores
- Weekly workload constraints
- Deadline, dependency, and conflict rules

The goal is to help users understand which projects can be completed, when they can be scheduled, and which workers are best suited for each role.

## Features

- Manual project and worker entry
- CSV/Excel project and worker import
- Editable project, worker, and Q-matrix tables
- Rule-based project-specific Q-matrix generation
- Adjustable objective weights and minimum Q-score threshold
- PuLP-based optimization
- Project deadline and duration scheduling
- Mandatory, dependency, and conflict project constraints
- Worker weekly-hour capacity constraints and unavailability handling
- Results summary with selected projects and assignments
- Worker weekly workload display
- Explanations for unselected projects
- Excel export of optimization results
- Local JSON save/load
- Access-code cloud saving/loading
- Logged-in user autosave and recovery
- Building blocks for AI-generated Q-matrix exist in the code, but are unavailable by default.

## Q Matrix

The Q matrix represents worker-project-role suitability. Each Q value estimates how suitable a worker is for a specific role within a specific project. This project-specific structure allows the same worker-role pair to receive different suitability scores across different projects.

## Main Workflow

1. Add or import project data.
2. Add or import worker data.
3. Generate the Q matrix.
4. Adjust optimization settings if needed.
5. Run the optimizer.
6. Review the results.
7. Export results if needed.
8. Save the scenario for later use at any time.

## Main Files

| File | Purpose |
| --- | --- |
| `app.py` | Main Streamlit interface and workflow |
| `optimizer.py` | PuLP optimization model |
| `q_generator.py` | Rule-based Q-matrix generation |
| `gemini_q_generator.py` | Optional Gemini-based Q-matrix generation |
| `helper_functions.py` | Data cleaning, input preparation, schedule handling, and result export helpers |
| `app_state_helpers.py` | Streamlit session state, login, autosave, and result-state helpers |
| `scenario_file_helpers.py` | Local JSON scenario save/load helpers |
| `cloud_save_helpers.py` | Supabase cloud save and autosave helpers |
| `role_keywords.py` | Loads role-library data from CSV |
| `role_library.csv` | Role descriptions, keywords, related roles, and scoring terms |

## Run Locally

Install the required packages:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python -m streamlit run app.py
```

## Notes

The deployed version may require Streamlit secrets for Supabase cloud saving, Google login, and the unactivated AI-generated Q-matrix generation. These are not included in the repository, so local testing requires your own credentials.

# Project Selection, Scheduling, and Role Assignment Prototype

This is a Streamlit prototype for project selection, scheduling, and role assignment. It uses a PuLP optimization model to help users select projects, assign workers to required project roles, and build a weekly schedule while considering deadlines, worker availability, weekly capacity, project dependencies, and project conflicts.

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
- Editable project and worker tables
- Rule-based Q-matrix generation
- Optional Gemini-based Q-matrix generation
- Adjustable objective weights and Q-score threshold
- PuLP-based optimization
- Project deadline and duration scheduling
- Mandatory, conflict, and dependency constraints
- Worker weekly-hour capacity and unavailability constraints
- Results summary with selected projects and assignments
- Worker weekly workload display
- Excel export of results

## Main Workflow

1. Add or import project data.
2. Add or import worker data.
3. Generate the Q matrix.
4. Run the optimizer.
5. Review the results.

## Results Export

After running the optimizer, the app can export results to Excel. It includes:

- Summary
- Optimization settings
- Schedule
- Assignments
- Unselected projects
- Worker workload
- Deadline details
- Project relationship rules

## Saving Progress
- progress can now be saved using a downloadable JSON file or through cloud saving on the sidebar.

## Run Locally

Install the required packages:

```bash
pip install -r requirements.txt

Run the application:

python -m streamlit run app_rev2.py

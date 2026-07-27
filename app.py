# Streamlit app for project selection, scheduling, role assignment, and results display.
# The optimization itself is handled in optimizer_rev2.py.

# Importing Streamlit for the user interface.
import streamlit as st

# Importing pandas to help convert saved lists of dictionaries into editable/displayable tables.
import pandas as pd

# Importing the optimizer file.
from optimizer import ProjectSelectionGMRA

# Importing helper functions.
import helper_functions as helper

# Importing the rule-based Q-matrix generator.
from q_generator import generate_q_matrix

# Importing the role library.
from role_keywords import load_role_library

# Importing experimental Gemini functions.
# from gemini_q_generator import generate_q_matrix_with_gemini, gemini_api_key_available

# Importing date for deadline calculations and calendar schedule display.
from datetime import date

import scenario_file_helpers as scenario_files

import cloud_save_helpers as cloud_save

import app_state_helpers as app_state

st.set_page_config(
    page_title="Project Scheduling and Role Assignment Optimizer",
    layout="wide"
)


app_state.handle_login_choice()


DEFAULT_WORKERS_PER_ROLE = 1
DEFAULT_ROLE_HOURS_PER_WEEK = 4

ENABLE_GEMINI_GENERATION = False # Set to true to enable gemimi generation code.


# Role library. Returns:
# - roles: role names
# - Role_Descriptions: descriptions for each role
# - Keywords: general profile keywords
# - Related_Skills: related roles/skills
# - Responsibilities: role tasks
# - Positive_Keywords
# - Negative_Keywords
(
    roles,
    Role_Descriptions,
    Keywords,
    Related_Skills,
    Responsibilities,
    Positive_Keywords,
    Negative_Keywords
) = load_role_library()


# Initialize Streamlit session state and restore autosaved data before widgets are created.
app_state.initialize_session_state()
app_state.restore_autosave_before_widgets()

# Main app title.
st.title("PSSRA Optimizer")
st.caption("Select projects, assign workers, and build a feasible weekly schedule based on deadlines, workload, dependencies, and conflicts.")

# -----------------------------
# SIDEBAR SETTINGS
# -----------------------------
with st.sidebar:
    st.header("Optimization Settings")

    start_date = st.date_input(
        "Start date",
        value=date.today(),
        key="start_date_input",
        help=(
            "This is the calendar date used for Week 1. "
            "The optimizer still uses week numbers internally."
        )
    )

    min_suitability = st.slider(
        "Minimum Q score required for assignment",
        min_value=0.0,
        max_value=1.0,
        value=0.30,
        step=0.05,
        key="min_suitability_input",
        help=(
            "Workers with a Q score below this value cannot be assigned that specific project. "
            "Higher values make assignment requirements stricter. Lower values make them more flexible."
        )
    )
    
    with st.expander("Advanced objective weights", expanded=False):

        alpha = st.slider(
            "Project completion bonus",
            min_value=0.0,
            max_value=1.0,
            value=0.25,
            step=0.05,
            key="completion_bonus_input",
            help=(
                "Higher values encourage selecting more projects. Lower values make the optimizer less sensitive to the number of projects selected."
            )
        )

        beta = st.slider(
            "Worker preference bonus",
            min_value=0.0,
            max_value=1.0,
            value=0.20,
            step=0.05,
            key="preference_bonus_input",
            help=(
                "Higher values encourage assigning workers to their preferred roles. Lower values make the optimizer less sensitive to worker preferences."
            )
        )

        delta = st.slider(
            "Project priority bonus",
            min_value=0.0,
            max_value=1.0,
            value=0.50,
            step=0.05,
            key="priority_bonus_input",
            help=(
                "Higher values encourage selecting higher-priority projects. Lower values make the optimizer less sensitive to project priority."
            )
        )

        gamma = st.slider(
            "Start week penalty",
            min_value=0.0,
            max_value=0.10,
            value=0.01,
            step=0.005,
            key="start_week_penalty_input",
            help=(
                "Higher values encourage starting projects earlier. Lower values make the optimizer less sensitive to start week."
            )
        )

        st.button(
            "Reset weights to default",
            on_click=app_state.reset_weights_to_default,
            help="Reset all objective weights to their default values."
        )

    st.divider()

    if st.session_state.pop("autosave_after_widgets_created", False):
        app_state.autosave_current_state(reason="scenario loaded")
        st.session_state.last_autosaved_settings_snapshot = app_state.get_current_settings()

        autosave_message = st.session_state.pop(
            "autosave_after_widgets_message",
            "Scenario loaded."
        )

        st.session_state.autosave_status_message = autosave_message
        st.session_state.autosave_status_type = "success"

    current_settings_snapshot = app_state.get_current_settings()

    if (
        app_state.current_app_has_content()
        and st.session_state.get("last_autosaved_settings_snapshot") != current_settings_snapshot
    ):
        st.session_state.last_autosaved_settings_snapshot = current_settings_snapshot
        app_state.autosave_current_state(reason="settings changed")

    st.metric("Projects", len(st.session_state.projects))
    st.metric("Workers", len(st.session_state.workers))
    st.metric("Q Matrix Rows", len(st.session_state.q_matrix))

    st.divider()

    with st.expander("Save Scenario Locally", expanded=False):
        st.caption(
            "Download a scenario file to save your current projects, workers, "
            "Q matrix, and settings. Upload the file later to continue from the same point."
        )

        # -----------------------------
        # DOWNLOAD CURRENT SCENARIO
        # -----------------------------
        st.markdown("#### Download Current Scenario")

        scenario_name = st.text_input(
            "Scenario name",
            placeholder="Example: August Planning Schedule",
            key="scenario_file_name_input"
        )

        scenario_has_content = (
            len(st.session_state.projects) > 0
            or len(st.session_state.workers) > 0
            or len(st.session_state.q_matrix) > 0
        )

        scenario_save_data = scenario_files.build_scenario_save_data(
            scenario_name=scenario_name,
            projects=st.session_state.projects,
            workers=st.session_state.workers,
            q_matrix=st.session_state.q_matrix,
            settings=app_state.get_current_settings()
        )

        st.download_button(
            "Download Scenario Save File",
            data=scenario_save_data,
            file_name=scenario_files.make_safe_filename(scenario_name),
            mime="application/json",
            use_container_width=True,
            disabled=not scenario_has_content,
            help="Download a JSON file that can be uploaded later to restore this scenario.",
            on_click="ignore"
        )

        if not scenario_has_content:
            st.info("Add projects, workers, or a Q matrix before downloading a scenario save file.")

        st.divider()

        # -----------------------------
        # UPLOAD SAVED SCENARIO
        # -----------------------------
        st.markdown("#### Upload Saved Scenario")

        st.file_uploader(
            "Upload scenario JSON file",
            type=["json"],
            key="scenario_file_upload",
            help="Upload a scenario save file that was previously downloaded from this app."
        )

        st.button(
            "Load Scenario File",
            on_click=app_state.load_scenario_from_uploaded_file,
            use_container_width=True
        )

        if "scenario_file_message" in st.session_state:
            message_type = st.session_state.get("scenario_file_message_type", "success")

            if message_type == "warning":
                st.warning(st.session_state.scenario_file_message)
            elif message_type == "error":
                st.error(st.session_state.scenario_file_message)
            else:
                st.success(st.session_state.scenario_file_message)

    with st.expander("Cloud Save", expanded=False):
        st.caption(
            "Experimental cloud save. Saves your current projects, workers, Q matrix, "
            "and settings to Supabase using an access code."
        )

        st.warning(
            "Prototype only: do not store sensitive real employee or student data."
        )

        cloud_scenario_name = st.text_input(
            "Cloud scenario name",
            placeholder="Example: August Planning Schedule",
            key="cloud_scenario_name_input"
        )

        cloud_access_code = st.text_input(
            "Access code",
            type="password",
            key="cloud_access_code_input",
            help="Use the same access code later to find and load your saved scenarios."
        )

        cloud_has_content = (
            len(st.session_state.projects) > 0
            or len(st.session_state.workers) > 0
            or len(st.session_state.q_matrix) > 0
        )

        if st.button(
            "Save Current Scenario to Cloud",
            disabled=not cloud_has_content,
            use_container_width=True
        ):
            try:
                scenario_data = scenario_files.build_scenario_dictionary(
                    scenario_name=cloud_scenario_name,
                    projects=st.session_state.projects,
                    workers=st.session_state.workers,
                    q_matrix=st.session_state.q_matrix,
                    settings=app_state.get_current_settings()
                )

                cloud_save.save_scenario_to_cloud(
                    scenario_name=cloud_scenario_name,
                    access_code=cloud_access_code,
                    scenario_json=scenario_data
                )

                app_state.set_cloud_save_message("Scenario saved to cloud.", "success")

            except Exception as error:
                app_state.set_cloud_save_message(f"Cloud save failed: {error}", "error")

        if not cloud_has_content:
            st.info("Add projects, workers, or a Q matrix before saving to cloud.")

        st.divider()

        if st.button("Find Cloud Saves", use_container_width=True):
            try:
                st.session_state.cloud_saved_scenarios = (
                    cloud_save.list_scenarios_for_access_code(cloud_access_code)
                )

                if len(st.session_state.cloud_saved_scenarios) == 0:
                    app_state.set_cloud_save_message("No cloud saves found for that access code.", "warning")
                else:
                    app_state.set_cloud_save_message("Cloud saves found.", "success")

            except Exception as error:
                app_state.set_cloud_save_message(f"Could not find cloud saves: {error}", "error")

        cloud_saved_scenarios = st.session_state.get("cloud_saved_scenarios", [])

        if len(cloud_saved_scenarios) > 0:
            scenario_options = {
                f"{row['scenario_name']} — updated {row.get('updated_at', '')}": row["id"]
                for row in cloud_saved_scenarios
            }

            selected_cloud_scenario_label = st.selectbox(
                "Saved cloud scenarios",
                options=list(scenario_options.keys()),
                key="selected_cloud_scenario_label"
            )

            selected_cloud_scenario_id = scenario_options[selected_cloud_scenario_label]

            if st.button("Load Selected Cloud Save", use_container_width=True):
                try:
                    scenario_data = cloud_save.load_scenario_from_cloud(
                        scenario_id=selected_cloud_scenario_id,
                        access_code=cloud_access_code
                    )

                    st.session_state.pending_scenario_to_apply = scenario_data
                    st.session_state.pending_scenario_message = "Cloud scenario loaded."

                    st.rerun()

                except Exception as error:
                    app_state.set_cloud_save_message(f"Cloud load failed: {error}", "error")

            if st.button("Delete Selected Cloud Save", use_container_width=True):
                try:
                    cloud_save.delete_scenario_from_cloud(
                        scenario_id=selected_cloud_scenario_id,
                        access_code=cloud_access_code
                    )

                    st.session_state.cloud_saved_scenarios = []
                    app_state.set_cloud_save_message("Cloud scenario deleted.", "success")

                except Exception as error:
                    app_state.set_cloud_save_message(f"Cloud delete failed: {error}", "error")

        if "cloud_save_message" in st.session_state:
            message_type = st.session_state.get("cloud_save_message_type", "success")

            if message_type == "warning":
                st.warning(st.session_state.cloud_save_message)
            elif message_type == "error":
                st.error(st.session_state.cloud_save_message)
            else:
                st.success(st.session_state.cloud_save_message)

    st.divider()

    st.markdown("### Autosave")

    if app_state.is_user_logged_in():
        if "autosave_status_message" in st.session_state:
            message_type = st.session_state.get("autosave_status_type", "success")

            if message_type == "error":
                st.error(st.session_state.autosave_status_message)
            elif message_type == "warning":
                st.warning(st.session_state.autosave_status_message)
            else:
                st.success(st.session_state.autosave_status_message)
        else:
            st.info("Autosave will begin after you add projects, workers, or a Q matrix.")

        if st.button("Autosave Now", use_container_width=True):
            app_state.autosave_current_state(reason="manual autosave")

    else:
        st.info("Autosave is disabled because you are not logged in.")

        if app_state.streamlit_auth_is_configured():
            if st.button("Log in to enable autosave", use_container_width=True):
                st.login()
        else:
            st.caption("Login is not configured for this deployment.")

    st.divider()

    st.markdown("### Clear Data")

    if app_state.is_user_logged_in():
        clear_warning_text = (
            "I understand this will clear all current app data and delete my autosaved recovery state."
        )
    else:
        clear_warning_text = (
            "I understand this will clear all current app data from this browser session."
        )

    confirm_clear_all = st.checkbox(
        clear_warning_text,
        key="confirm_clear_all_data"
    )

    if st.button(
        "Clear All Data",
        use_container_width=True,
        disabled=not confirm_clear_all
    ):
        app_state.clear_all_app_data()
        st.rerun()

    if app_state.is_user_logged_in():
        st.caption(f"Logged in as {app_state.get_logged_in_user_email()}")

        if st.button("Log out"):
            st.logout()
    else:
        st.caption("Using app without login. Autosave recovery is disabled.")

# -----------------------------
# PAGE NAVIGATION
# -----------------------------
PAGE_ORDER = ["Overview", "Projects", "Workers", "Q Matrix", "Results", "Feedback"]

if "active_page" not in st.session_state:
    st.session_state.active_page = "Overview"

def go_to_page(page_name):
    st.session_state.active_page = page_name

active_page = st.radio(
    "Go to section",
    PAGE_ORDER,
    index=PAGE_ORDER.index(st.session_state.active_page),
    horizontal=True,
    key="active_page",
    label_visibility="collapsed"
)


# -----------------------------
# OVERVIEW TAB
# -----------------------------
if active_page == "Overview":
    st.subheader("Overview")

    st.write(
        """
        This prototype supports project selection, scheduling, and role assignment for a small department.
        Users can enter or import projects and workers, generate a suitability-based Q matrix, review or edit Q values,
        and run an optimization model to select projects and assign workers to roles.
        """
    )

    st.info(
        "Tip: Many fields include a small question-mark help icon. Hover over these icons for guidance on what each input means."
    )

    st.markdown("### Instructions")

    st.markdown(
        """
        1. Add or import projects.
        2. Add or import workers.
        3. Generate the Q matrix using the rule-based role library.
        4. Review or edit Q values before optimization.
        5. Run the optimizer and review the selected projects, schedule, assignments, and workload.
        """
    )

    st.markdown("### How to Interpret the Results")

    st.markdown(
        """
        After optimization, the app shows which projects were selected, when each project starts,
        which weeks each project is active, which workers were assigned to each required role,
        and how many weekly project hours each worker uses.

        A project may not be selected if there are not enough qualified workers, if Q scores are below the minimum assignment threshold,
        or if deadline, dependency, conflict, availability, or workload constraints make the schedule fail.
        """
    )

    with st.expander("Current features"):
        st.markdown(
            """
            - Manual project and worker entry
            - CSV/Excel project and worker import
            - Editable project and worker tables
            - Role-library-based Q-matrix generation
            - Editable Q matrix before optimization
            - Adjustable minimum Q-score threshold
            - PuLP-based project selection and role assignment
            - Mandatory project constraints
            - Dependency constraints with finish-before-start scheduling
            - Conflict constraints using non-overlap scheduling
            - Worker weekly-hour usage results
            - Role-specific hours with a default fallback value
            """
        )

    st.markdown("### Notes")

    st.info(
        "Generated Q values are initial rule-based estimates. Users should review and/or adjust them before running optimization."
    )

    st.divider()

    st.button(
        "Continue to Projects",
        on_click=go_to_page,
        args=("Projects",),
    )

# -----------------------------
# PROJECTS TAB
# -----------------------------
if active_page == "Projects":
    st.subheader("Project Selection")
    st.caption("Add projects manually or import a project list from CSV/Excel.")

    # Build a list of existing project names so a new projects can reference existing projects.
    existing_projects = [
        project.get("Project name", "") for project in st.session_state.projects
        if str(project.get("Project name", "")).strip() != ""
    ]

    # Form for entering one project at a time (manual entry).
    with st.form("project_form", clear_on_submit=True):
        # Text input for project name.
        name = st.text_input(
            "Project name:",
            key="project_name_input",
            help="Enter the name of the project."
        )

        project_context = st.text_area(
            "Project context / description:",
            key="project_context_input",
            help="Describe the project's purpose, requirements, and/or keywords. Used for Q-matrix generation."
        )

        # Slider input for project priority.
        priority = st.slider(
            "Project priority:",
            min_value=1,
            max_value=3,
            value=1,
            key="project_priority_input",
            help="Set the importance of the project. Higher priority projects will have higher weight in the optimizer."
        )

        # Date input for the project deadline.
        deadline = st.date_input(
            "Project deadline:",
            value=None,
            key="project_deadline_input",
            help="Input the date of the project deadline."
        )

        # Number input for the estimated project duration in weeks.
        estimated_duration = st.number_input(
            "Estimated duration in weeks:",
            min_value=1,
            max_value=52,
            value=1,
            step=1,
            key="project_duration_input",
            help="Enter how many weeks the project is expected to take to complete."
        )

        # Multiselect input for required roles.
        selected_roles = st.multiselect(
            "Project roles:",
            options=roles,
            key="project_roles_input",
            help="Enter the roles that the project needs."
        )

        workers_per_role_text = st.text_input(
            f"Workers needed per role (optional, default: {DEFAULT_WORKERS_PER_ROLE}):",
            placeholder=f"Example: Project Manager: 1, Programmer: 2. Default: {DEFAULT_WORKERS_PER_ROLE} worker per selected role.",
            key="workers_per_role_input",
            help=f"If left blank, each selected role defaults to {DEFAULT_WORKERS_PER_ROLE} worker."
        )

        specific_role_hours_text = st.text_input(
            f"Role hours per week (optional, default: {DEFAULT_ROLE_HOURS_PER_WEEK}):",
            placeholder=f"Example: Project Manager: 4, Programmer: 6. Default: {DEFAULT_ROLE_HOURS_PER_WEEK} hours/week per selected role.",
            key="specific_role_hours_input",
            help=f"If left blank, each selected role defaults to {DEFAULT_ROLE_HOURS_PER_WEEK} hours/week."
        )

        st.info(
            f"Defaults: if left blank, the app will use "
            f"{DEFAULT_WORKERS_PER_ROLE} worker per selected role and "
            f"{DEFAULT_ROLE_HOURS_PER_WEEK} hours/week per selected role. "
            f"These defaults will appear in the project table after submission."
        )

        with st.expander("Advanced project relationship rules"):
            
            # Checkbox for marking a project as mandatory.
            mandatory = st.checkbox(
                "Mandatory project (optional)",
                key="project_mandatory_input",
                help="Check if the project is mandatory and MUST be completed."
            )

            # Allows the user to choose existing projects that this new project depends on.
            depends_on = st.multiselect(
                "Depends on existing projects (optional):",
                options=existing_projects,
                key="project_depends_on_input",
                help="Choose existing projects that need to be completed before this project can begin. Projects must have already been submitted to appear here."
            )

            # Allows the user to choose existing projects that conflict with this new project.
            conflicts_with = st.multiselect(
                "Conflicts with existing projects (optional):",
                options=existing_projects,
                key="project_conflicts_with_input",
                help="Choose existing projects that cannot be active at the same time as this project. Projects must have already been submitted to appear here."
            )

        # Submit button for the manual project form.
        submit_project = st.form_submit_button("Submit Project")

    # Validate and save project information after the manual submit button is pressed.
    if submit_project:
        # Project name is required.
        if name.strip() == "":
            st.warning("Please input a project name.")

        # At least one required role must be selected.
        elif len(selected_roles) == 0:
            st.warning("Please select at least one role.")

        
        # If input is valid, create and save the project.
        else:

            completed_workers_per_role_text = helper.complete_role_value_text(
                selected_roles=selected_roles,
                input_text=workers_per_role_text,
                default_value=DEFAULT_WORKERS_PER_ROLE,
                value_type="int"
            )

            completed_specific_role_hours_text = helper.complete_role_value_text(
                selected_roles=selected_roles,
                input_text=specific_role_hours_text,
                default_value=DEFAULT_ROLE_HOURS_PER_WEEK,
                value_type="float"
            )

            if workers_per_role_text.strip() == "":
                st.info(
                    f"No workers-per-role values entered. "
                    f"The app used the default of {DEFAULT_WORKERS_PER_ROLE} worker per selected role."
                )

            if specific_role_hours_text.strip() == "":
                st.info(
                    f"No role-hour values entered. "
                    f"The app used the default of {DEFAULT_ROLE_HOURS_PER_WEEK} hours/week per selected role."
                )

            # Store one project as a dictionary.
            # Roles and relationships are stored as comma-separated text.
            new_project = {
                "Project name": name,
                "Project context": project_context,
                "Priority": priority,
                "Roles": ", ".join(selected_roles),
                "Workers per role": completed_workers_per_role_text,
                "Role hours per week": completed_specific_role_hours_text,
                "Role hours/week": DEFAULT_ROLE_HOURS_PER_WEEK,  # hidden fallback
                "Mandatory": mandatory,
                "Deadline": deadline,
                "Estimated duration (weeks)": estimated_duration,
                "Depends on": ", ".join(depends_on),
                "Conflicts with": ", ".join(conflicts_with),
                "Uploaded file": "Manual entry"
            }

            # Add project only if it is not already in the stored list.
            if new_project not in st.session_state.projects:
                st.session_state.projects.append(new_project)

                # Clearing old Q matrix.
                st.session_state.q_matrix = []

                st.success("Project added.")
                app_state.autosave_current_state(reason="project added")

            else:
                st.warning("This project has already been added.")

    # Project file import section.
    st.divider()
    st.subheader("Import projects")

    with st.expander("Import projects from CSV/Excel"):
        st.text("Download project template:")
        with open("templates/project_template.xlsx", "rb") as file:
            st.download_button(
                "Project Template",
                file,
                "projects_template.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        uploaded_project_file = st.file_uploader(
            "Upload project CSV or Excel file:",
            type=["csv", "xlsx"],
            key="project_csv_upload",
            help="Required columns are Project name, Priority, Roles in that format."
            " Optional columns include Project context, Workers per role, Role hours per week, Mandatory, Deadline, Estimated duration (weeks), Depends on, Conflicts with, Uploaded file."
        )

        # If a project file has been uploaded, show the uploaded file name.
        if uploaded_project_file is not None:
            st.info(f"Uploaded file: {uploaded_project_file.name}")

            st.caption("Press the button below to import the project file. The number of added projects will appear in the sidebar.")

            # Import button for the project file.
            if st.button("Import Project File", key="import_project_file_button"):
                imported_projects = helper.load_projects_from_file(uploaded_project_file)

                # If valid projects were imported, complete default values and add them to the project list.
                if len(imported_projects) > 0:
                    imported_projects = helper.apply_project_defaults(
                        imported_projects,
                        default_workers_per_role=DEFAULT_WORKERS_PER_ROLE,
                        default_role_hours_per_week=DEFAULT_ROLE_HOURS_PER_WEEK
                    )

                    st.session_state.projects.extend(imported_projects)
                    st.session_state.q_matrix = []

                    st.session_state.projects_editor_version += 1
                    st.session_state.q_matrix_editor_version += 1

                    st.success(f"Imported {len(imported_projects)} projects.")
                    app_state.autosave_current_state(reason="projects imported")
                    st.rerun()

    # Clear all saved projects.
    if st.button("Clear Projects"):
        st.session_state.projects = []
        st.session_state.q_matrix = []

        st.session_state.projects_editor_version += 1
        st.session_state.q_matrix_editor_version += 1

        st.success("Projects cleared.")
        app_state.autosave_current_state(reason="projects cleared", delete_if_empty=True)
        st.rerun()

    # Display current saved projects.
    st.subheader("Entered projects")

    # Complete defaults for imported projects and table-edited rows before display.
    st.session_state.projects = helper.clean_records(
        helper.apply_project_defaults(
            st.session_state.projects,
            default_workers_per_role=DEFAULT_WORKERS_PER_ROLE,
            default_role_hours_per_week=DEFAULT_ROLE_HOURS_PER_WEEK
        )
    )

    # Convert project records into a Pandas DataFrame for table editing.
    projects_df = pd.DataFrame(st.session_state.projects)

    # Hide the internal fallback column from the user-facing table.
    # "Role hours/week" is still kept in the background and restored before saving.
    display_projects_df = projects_df.drop(
        columns=["Role hours/week", "Uploaded file"],
        errors="ignore"
    )

    # Editable table for projects.
    edited_projects_df = st.data_editor(
        display_projects_df,
        num_rows="dynamic",
        key=f"projects_editor_{st.session_state.projects_editor_version}",
        use_container_width=True
    )

    # Save edited table rows back into session state.
    # Complete default values and restore the hidden fallback value so the optimizer
    # still has a default if a role is missing from "Role hours per week".
    edited_project_records = helper.apply_project_defaults(
        edited_projects_df.to_dict("records"),
        default_workers_per_role=DEFAULT_WORKERS_PER_ROLE,
        default_role_hours_per_week=DEFAULT_ROLE_HOURS_PER_WEEK
    )

    cleaned_project_records = helper.clean_records(edited_project_records)

    if cleaned_project_records != st.session_state.projects:
        st.session_state.projects = cleaned_project_records
        st.session_state.q_matrix = []
        st.session_state.q_matrix_editor_version += 1
        app_state.autosave_current_state(reason="project table edited", delete_if_empty=True)
    else:
        st.session_state.projects = cleaned_project_records

    st.divider()

    st.button(
        "Continue to Workers",
        on_click=go_to_page,
        args=("Workers",),
    )

# -----------------------------
# WORKERS TAB
# -----------------------------
if active_page == "Workers":
    st.subheader("Worker Details")
    st.caption("Add workers manually or import a worker list from CSV/Excel.")

    # Form for manual worker entry.
    with st.form("worker_form", clear_on_submit=True):
        # Text input for worker name.
        worker_name = st.text_input(
            "Worker name:",
            key="worker_name_input",
            help="Enter the worker's name."
        )

        # Text area for worker profile/experience.
        worker_profile = st.text_area(
            "Worker profile / experience:",
            key="worker_profile_input",
            help="Describe the worker's experience, backgrounds, and/or skills."
        )

        # Multiselect input for worker skills.
        worker_skills = st.multiselect(
            "Worker skills:",
            options=roles,
            key="worker_skills_input",
            help="Select the roles or skills this worker has."
        )

        # Multiselect input for worker role preferences.
        worker_role_preferences = st.multiselect(
            "Worker preferred roles (optional):",
            options=roles,
            key="worker_preferences_input",
            help="Select roles the worker would prefer above others."
        )

        # Weekly capacity hours = estimated hours per week the worker can spend on projects.
        weekly_hours = st.number_input(
            "Worker weekly capacity in hours:",
            min_value=1,
            max_value=45,
            value=5,
            key="weekly_hours_input",
            help="Enter how many hours per week the worker can spend on projects."
        )

        # Unavailability weeks or dates for workers.
        worker_unavailability = st.text_input(
            "Unavailability (optional):",
            placeholder="Examples: 3, 4, 8 OR 2026-08-10 to 2026-08-15, 2026-08-21",
            key="worker_unavailability_input",
            help="Enter the week numbers or date ranges (YYYY-MM-DD) the worker cannot work. Week 1 starts on the selected date in the sidebar."
        )

        # Submit button for the manual worker form.
        submit_worker = st.form_submit_button("Submit Worker")

    # Validate and save worker information after submit button is pressed.
    if submit_worker:
        # Worker name is required.
        if worker_name.strip() == "":
            st.warning("Please input a worker name.")

        # Worker profile is required.
        elif worker_profile.strip() == "":
            st.warning("Please input a worker profile.")

        # At least one worker skill needed.
        elif len(worker_skills) == 0:
            st.warning("Please select at least one skill.")

        # If input is valid, create and save the worker.
        else:
            # Store worker as a dictionary.
            new_worker = {
                "Worker name": worker_name,
                "Profile": worker_profile,
                "Skills": ", ".join(worker_skills),
                "Preferred roles": ", ".join(worker_role_preferences),
                "Weekly hours": weekly_hours,
                "Unavailability": worker_unavailability,
                "Uploaded profile": "Manual entry"
            }

            # Add worker only if they are not already in the stored list.
            if new_worker not in st.session_state.workers:
                st.session_state.workers.append(new_worker)

                # Clearing old Q matrix.
                st.session_state.q_matrix = []

                st.success("Worker added.")
                app_state.autosave_current_state(reason="worker added")

            else:
                st.warning("This worker has already been added.")

    # Worker file import section.
    st.divider()
    st.subheader("Import workers")

    with st.expander("Import workers from CSV/Excel"):
        st.text("Download worker template:")
        with open("templates/worker_template.xlsx", "rb") as file:
            st.download_button(
                "Worker Template",
                file,
                "workers_template.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        uploaded_worker_file = st.file_uploader(
            "Upload worker CSV or Excel file:",
            type=["csv", "xlsx"],
            key="worker_csv_upload",
            help="Required columns are Worker name, Profile, Skills, Weekly hours in that format."
            " Optional columns are Preferred roles and Unavailability."
        )

        # If a worker file has been uploaded, show the uploaded file name.
        if uploaded_worker_file is not None:
            st.info(f"Uploaded file: {uploaded_worker_file.name}")

            st.caption("Press the button below to import the worker file. The number of added workers will be shown in the sidebar.")

            # Import button for the worker file.
            if st.button("Import Worker File", key="import_worker_file_button"):
                imported_workers = helper.load_workers_from_file(uploaded_worker_file)

                # If valid workers were imported, add them to the stored worker list.
                if len(imported_workers) > 0:
                    st.session_state.workers.extend(imported_workers)
                    st.session_state.q_matrix = []

                    st.session_state.workers_editor_version += 1
                    st.session_state.q_matrix_editor_version += 1

                    st.success(f"Imported {len(imported_workers)} workers.")
                    app_state.autosave_current_state(reason="workers imported")
                    st.rerun()

    # Clear all saved workers.
    if st.button("Clear Workers"):
        st.session_state.workers = []
        st.session_state.q_matrix = []

        st.session_state.workers_editor_version += 1
        st.session_state.q_matrix_editor_version += 1

        st.success("Workers cleared.")
        app_state.autosave_current_state(reason="workers cleared", delete_if_empty=True)
        st.rerun()

    # Display saved workers.
    st.subheader("Entered workers")

    # Convert worker records into a Pandas DataFrame for table editing.
    workers_df = pd.DataFrame(st.session_state.workers)

    workers_df = workers_df.drop(
        columns=["Uploaded profile"],
        errors="ignore"
    )

    # Editable table for workers.
    edited_workers_df = st.data_editor(
        workers_df,
        num_rows="dynamic",
        key=f"workers_editor_{st.session_state.workers_editor_version}",
        use_container_width=True
    )

    # Save edited table rows back into session state.
    cleaned_worker_records = helper.clean_records(
        edited_workers_df.to_dict("records")
    )

    if cleaned_worker_records != st.session_state.workers:
        st.session_state.workers = cleaned_worker_records
        st.session_state.q_matrix = []
        st.session_state.q_matrix_editor_version += 1
        app_state.autosave_current_state(reason="worker table edited", delete_if_empty=True)
    else:
        st.session_state.workers = cleaned_worker_records

    st.divider()

    st.button(
        "Continue to Q Matrix",
        on_click=go_to_page,
        args=("Q Matrix",),
    )

# -----------------------------
# Q MATRIX TAB
# -----------------------------
if active_page == "Q Matrix":
    st.subheader("Q Matrix Generation")
    st.caption("Generate suitability scores, review them, and edit values before optimization.")

    # Generate the Q matrix using the rule-based Q-generation.
    if st.button("Generate Q Matrix"):
        # Need at least one project before generating Q.
        if len(st.session_state.projects) == 0:
            st.warning("Please add at least one project first.")

        # Need at least one worker before generating Q.
        elif len(st.session_state.workers) == 0:
            st.warning("Please add at least one worker first.")

        # If projects and workers exist, generate and save Q matrix rows.
        else:
            st.session_state.q_matrix = generate_q_matrix(
                st.session_state.workers,
                st.session_state.projects
            )

            st.session_state.q_matrix_editor_version += 1

            st.success("Q matrix generated from worker skills, profiles, roles, and project context.")
            app_state.autosave_current_state(reason="q matrix generated")
    
    st.caption("Creates initial qualification scores using worker profiles, skills, project roles, and the role library.")

#    if ENABLE_GEMINI_GENERATION:
#
#        try:
#            from gemini_q_generator import generate_q_matrix_with_gemini, gemini_api_key_available
#
#            # Check whether a Gemini API key is available.
#            if gemini_api_key_available():
#                st.success("Gemini API key detected.")
#
#                # Optional AI-based Q-generation button.
#                if st.button("Generate Q Matrix with Gemini"):
#                    
#                    # Warn users that Gemini is experimental and may use API quota.
#                    st.warning("Warning: experimental. Gemini Q generation may use API quota and should be reviewed before optimization.")
#
#                    # Checking if projects and workers have been inputted.
#                    if len(st.session_state.projects) == 0:
#                        st.warning("Please add at least one project first.")
#                    elif len(st.session_state.workers) == 0:
#                        st.warning("Please add at least one worker first.")
#                    else:
#                        try:
#                            # Generate Q values using Gemini.
#                            gemini_rows = generate_q_matrix_with_gemini(
#                                st.session_state.workers,
#                                st.session_state.projects,
#                                roles,
#                                Role_Descriptions,
#                                Keywords,
#                                Related_Skills
#                            )
#
#                            # Save the Gemini-generated rows.
#                            st.session_state.q_matrix = gemini_rows
#
#                            st.success(
#                                f"Q matrix generated with Gemini. Rows generated: {len(st.session_state.q_matrix)}"
#                            )
#
#                            # Rerun the app so generated Q matrix appears.
#                            st.rerun()
#
#                        # If Gemini fails, show the error without crashing the app.
#                        except Exception as e:
#                            st.error("Gemini Q generation failed. The model may not have returned valid JSON.")
#                            st.write(str(e))
#                            st.info("Try again with fewer workers/projects, or use the rule-based generator.")
#                    
#                    st.caption("Uses Gemini to estimate Q scores.")
#
#            else:
#                st.info("Gemini API key not detected. Rule-based Q generation is available.")
#
#        except Exception as e:
#            st.info("Gemini Q generation is currently unavailable. Rule-based Q generation is available.")
        
    st.divider()

    # If Q matrix has been generated, display it.
    if len(st.session_state.q_matrix) > 0:
        st.subheader("Q matrix")

        # Convert saved Q-matrix rows into a DataFrame.
        # Convert saved Q-matrix rows into a DataFrame.
        full_q_df = pd.DataFrame(st.session_state.q_matrix)

        project_filter_options = ["All projects"] + sorted(
            full_q_df["Project"].dropna().unique().tolist()
        )

        selected_q_project = st.selectbox(
            "Filter Q matrix by project",
            options=project_filter_options,
            key="q_project_filter"
        )

        display_q_df = full_q_df.copy()

        if selected_q_project != "All projects":
            display_q_df = display_q_df[display_q_df["Project"] == selected_q_project]

        display_q_df = display_q_df.sort_values(
            by=["Project", "Role", "Q Value", "Worker"],
            ascending=[True, True, False, True]
        ).reset_index(drop=True)

        edited_q_df = st.data_editor(
            display_q_df,
            num_rows="fixed",
            key=f"q_matrix_editor_{st.session_state.q_matrix_editor_version}",
            use_container_width=True,
            hide_index=True
        )

        if st.button("Save Q Matrix"):
            if selected_q_project == "All projects":
                st.session_state.q_matrix = edited_q_df.to_dict("records")
            else:
                remaining_q_df = full_q_df[full_q_df["Project"] != selected_q_project]

                combined_q_df = pd.concat(
                    [remaining_q_df, edited_q_df],
                    ignore_index=True
                )

                st.session_state.q_matrix = combined_q_df.to_dict("records")

            st.success("Q matrix saved.")
            app_state.autosave_current_state(reason="q matrix saved")
        st.caption("Click Save Q Matrix to store these Q values for optimization.")

        # Clear current Q matrix if user wants to regenerate it.
        if st.button("Clear Saved Q Matrix"):
            st.session_state.q_matrix = []
            st.session_state.q_matrix_editor_version += 1

            if "q_project_filter" in st.session_state:
                del st.session_state.q_project_filter

            st.success("Saved Q matrix cleared.")
            app_state.autosave_current_state(reason="q matrix cleared", delete_if_empty=True)
            st.rerun()
        st.caption("Delete the saved Q matrix.")

    else:
        st.info("Add projects and workers, then generate a Q matrix.")

    st.divider()

    st.button(
        "Continue to Optimization Results",
        on_click=go_to_page,
        args=("Results",)    
        )

    st.divider()

    # Display the role library for reference.
    st.subheader("Role library")
    st.caption("List of existing roles within the system.")

    with st.expander("View current role library"):
        role_library_rows = []

        # Convert role library into table rows.
        for role in roles:
            role_library_rows.append({
                "Role": role,
                "Description": Role_Descriptions.get(role, ""),
                "Responsibilities": ", ".join(Responsibilities.get(role, [])),
                "Keywords": ", ".join(Keywords.get(role, [])),
                "Positive keywords": ", ".join(Positive_Keywords.get(role, [])),
                "Negative keywords": ", ".join(Negative_Keywords.get(role, [])),
                "Related roles": ", ".join(Related_Skills.get(role, []))
            })

        # Show the role library table.
        st.dataframe(role_library_rows, use_container_width=True, hide_index=True)

# -----------------------------
# RESULTS TAB
# -----------------------------
if active_page == "Results":
    st.subheader("Optimization Results")
    st.caption("Run the optimizer and review the selected projects, schedule, assignments, and workload.")
    st.warning("If you edited projects or workers, regenerate the Q matrix before running optimization.")


    # Ensuring everyhting has been inputted/completed before showing results.
    st.markdown("### Readiness Check")

    def check_icon(condition):
        return "✅" if condition else "❌"

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(f"{check_icon(len(st.session_state.projects) > 0)} Projects added")

    with col2:
        st.write(f"{check_icon(len(st.session_state.workers) > 0)} Workers added")

    with col3:
        st.write(f"{check_icon(len(st.session_state.q_matrix) > 0)} Q matrix saved")

    st.caption(
        f"Current minimum Q score required for assignment: {st.session_state.min_suitability_input}"
    )

    st.divider()

    # Button that runs the optimization model using the current saved data.
    if st.button("Run Optimization"):
        # The optimizer needs at least one project.
        if len(st.session_state.projects) == 0:
            st.warning("Please add at least one project first.")

        # The optimizer needs at least one worker.
        elif len(st.session_state.workers) == 0:
            st.warning("Please add at least one worker first.")

        # The optimizer needs a saved Q matrix.
        elif len(st.session_state.q_matrix) == 0:
            st.warning("Please save a Q matrix first.")

        # If all required inputs exist, run optimization.
        else:
            # Convert Streamlit project rows into optimizer project dictionary.
            projects_data = helper.build_projects(st.session_state.projects, planning_start_date=start_date)

            # Convert Streamlit worker rows into optimizer worker list.
            workers_data = helper.build_workers(st.session_state.workers)

            # Convert Streamlit worker rows into optimizer preferences dictionary.
            worker_preferences_data = helper.build_worker_preferences(st.session_state.workers)

            # Convert worker rows into a dictionary of available weekly project hours.
            weekly_hours_data = helper.build_weekly_hours(st.session_state.workers)

            # Convert worker rows into a dictionary of unavailability.
            worker_unavailability_data = helper.build_worker_unavailability(st.session_state.workers)

            # Convert date style unavailability into week-specific capacity reductions.
            worker_weekly_capacity_data = helper.build_worker_weekly_capacity(worker_rows=st.session_state.workers, 
                                                                              planning_start_date=start_date)

            # Convert Streamlit Q rows into nested optimizer Q dictionary.
            q_data = helper.build_q_matrix(st.session_state.q_matrix)

            # Build a list of projects that must be selected.
            mandatory_projects = helper.build_mandatory_projects(st.session_state.projects)

            deadline_blocked_mandatory_projects = [
                project
                for project in mandatory_projects
                if projects_data.get(project, {}).get("deadline_feasible", True) is False
            ]

            mandatory_projects_for_optimizer = [
                project
                for project in mandatory_projects
                if project not in deadline_blocked_mandatory_projects
            ]

            if len(deadline_blocked_mandatory_projects) > 0:
                st.warning(
                    "Some mandatory projects could not be forced into the schedule because "
                    "they cannot finish before their deadline. They will be shown as unselected "
                    "with an explanation."
                )

            # Build dependency constraints in the format:
            # (dependent_project, required_project).
            project_dependencies = helper.build_project_dependencies(st.session_state.projects)

            # Build conflict constraints in the format:
            # (project_a, project_b).
            project_conflicts = helper.build_project_conflicts(st.session_state.projects)

            # Create the optimization model using the user-entered data.
            model = ProjectSelectionGMRA(
                workers=workers_data,
                projects=projects_data,
                Q=q_data,
                project_dependencies=project_dependencies,
                project_conflicts=project_conflicts,
                mandatory_projects=mandatory_projects_for_optimizer,
                weekly_hours=weekly_hours_data,
                worker_preferences=worker_preferences_data,
                worker_unavailability=worker_unavailability_data,
                worker_weekly_capacity=worker_weekly_capacity_data,
                min_suitability=st.session_state.min_suitability_input,
                alpha=st.session_state.completion_bonus_input,
                beta=st.session_state.preference_bonus_input,
                delta=st.session_state.priority_bonus_input,
                gamma=st.session_state.start_week_penalty_input
            )

            # Solve the model and return selected projects, role assignments, objective score, and the optimizer-chosen project schedule.
            selected_projects, assignments, objective_score, project_schedule = model.resolve()

            if objective_score is None:
                st.error(
                    "No solution found. Try lowering the minimum Q score, increasing worker weekly hours, "
                    "removing mandatory requirements, or adjusting deadlines/availability."
                )
                st.stop()

            # Build weekly workload rows based on the optimizer's selected schedule.
            weekly_hours_usage_rows = helper.build_weekly_hours_usage(
                assignments,
                projects_data,
                weekly_hours_data,
                project_schedule,
                worker_unavailability_data,
                worker_weekly_capacity_data
            )

            # Display message if optimization worked.
            st.success("Optimization successful.")

            # -----------------------------
            # SUMMARY METRICS
            # -----------------------------
            st.markdown("### Summary")

            # Count how many projects were entered by the user.
            total_entered_projects = len(projects_data)

            # Count how many projects were selected by the optimizer.
            total_selected_projects = len(selected_projects)

            # Count how many worker-role assignments were actually made.
            # Assignments are now stored as lists because a role may need multiple workers.
            total_assignments = sum(
                len(assigned_workers) if isinstance(assigned_workers, list) else 1
                for project_assignments in assignments.values()
                for assigned_workers in project_assignments.values()
            )

            # Count how many worker-role assignments are required for selected projects.
            # This uses role_requirements so roles needing 2+ workers are counted correctly.
            total_required_roles_for_selected_projects = sum(
                int(projects_data[project].get("role_requirements", {}).get(role, 1))
                for project in selected_projects
                for role in projects_data[project]["required_roles"]
            )

            st.markdown("### What happened?")

            st.write(
                f"The optimizer selected **{total_selected_projects} out of {total_entered_projects}** projects "
                f"and made **{total_assignments} role assignments**."
            )

            st.write(
                "The schedule below shows when each selected project is planned to run. "
                "Detailed deadline rules, project relationships, and worker workload information are available in the expandable sections below."
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Selected Projects",
                    f"{total_selected_projects} / {total_entered_projects}"
                )
                st.caption("Projects selected out of total entered projects.")

            with col2:
                st.metric(
                    "Role Assignments",
                    f"{total_assignments} / {total_required_roles_for_selected_projects}"
                )
                st.caption("Total role assignments for selected projects.")

            with col3:
                st.metric("Objective Score", f"{objective_score:.2f}")
                st.caption("Overall optimization score.")

            with st.expander("Optimization settings used", expanded=False):
                st.write(f"Minimum Q score: {st.session_state.min_suitability_input}")
                st.write(f"Project completion bonus: {st.session_state.completion_bonus_input}")
                st.write(f"Worker preference bonus: {st.session_state.preference_bonus_input}")
                st.write(f"Project priority bonus: {st.session_state.priority_bonus_input}")
                st.write(f"Start week penalty: {st.session_state.start_week_penalty_input}")

            # Export button location
            export_placeholder = st.empty()

            st.divider()

            unselected_project_explanations = helper.explain_unselected_projects(
                all_projects=list(projects_data.keys()),
                selected_projects=selected_projects,
                projects_data=projects_data,
                workers_data=workers_data,
                q_data=q_data,
                project_dependencies=project_dependencies,
                project_conflicts=project_conflicts,
                project_schedule=project_schedule,
                min_suitability=st.session_state.min_suitability_input,
                weekly_hours=weekly_hours_data,
            )

            st.markdown("### Why some projects were not selected")

            st.info(
                "Projects may be unselected because of Q-score thresholds, worker weekly capacity, "
                "deadlines, dependencies, conflicts, or because selecting other projects produced a better overall objective score."
            )

            if len(unselected_project_explanations) > 0:
                st.dataframe(
                    unselected_project_explanations,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("All entered projects were selected.")

            # -----------------------------
            # MAIN SCHEDULE OVERVIEW
            # -----------------------------
            st.markdown("### Schedule Overview")
            st.caption(
                "This table shows the projects selected by the optimizer, when they are scheduled, "
                "and which roles are required."
            )

            main_results_rows = []

            for project in selected_projects:
                active_weeks = project_schedule.get(project, {}).get("Scheduled Active Weeks", [])

                if active_weeks:
                    active_weeks = sorted(active_weeks)

                    first_week = active_weeks[0]
                    last_week = active_weeks[-1]

                    calendar_date_range = helper.week_to_date_range(first_week, start_date).split(" to ")[0]
                    calendar_date_range += " to "
                    calendar_date_range += helper.week_to_date_range(last_week, start_date).split(" to ")[1]

                    if active_weeks == list(range(first_week, last_week + 1)):
                        active_week_display = f"{first_week}–{last_week}"
                    else:
                        active_week_display = ", ".join(str(week) for week in active_weeks)
                else:
                    active_week_display = ""
                    calendar_date_range = ""

                main_results_rows.append({
                    "Project": project,
                    "Total Priority": projects_data[project].get(
                        "effective_priority",
                        projects_data[project]["priority"]
),                  "Start Week": project_schedule.get(project, {}).get("Start Week", ""),
                    "Active Weeks": active_week_display,
                    "Calendar Dates": calendar_date_range,
                    "Required Roles": ", ".join(projects_data[project]["required_roles"])
                })

            if len(main_results_rows) > 0:
                st.dataframe(main_results_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No projects were selected.")

            st.divider()


            # -----------------------------
            # ASSIGNMENTS BY PROJECT
            # -----------------------------
            st.markdown("### Assignments by Project")
            st.caption("Open a project to see which worker was assigned to each required role.")

            assignment_rows = []

            for project, project_assignments in assignments.items():
                specific_role_hours = projects_data[project].get("specific_role_hours", {})
                default_role_hours = projects_data[project].get("role_hours_per_week", DEFAULT_ROLE_HOURS_PER_WEEK)

                for role, assigned_workers in project_assignments.items():
                    role_hours = specific_role_hours.get(role, default_role_hours)

                    if not isinstance(assigned_workers, list):
                        assigned_workers = [assigned_workers]

                    assignment_rows.append({
                        "Project": project,
                        "Role": role,
                        "Assigned Workers": ", ".join(str(worker) for worker in assigned_workers),
                        "Workers Assigned": len(assigned_workers),
                        "Hours/Week Each": role_hours,
                        "Total Role Hours/Week": role_hours * len(assigned_workers)
                    })

            for project, project_assignments in assignments.items():
                with st.expander(project, expanded=False):
                    specific_role_hours = projects_data[project].get("specific_role_hours", {})
                    default_role_hours = projects_data[project].get("role_hours_per_week", DEFAULT_ROLE_HOURS_PER_WEEK)

                    if len(project_assignments) == 0:
                        st.info("No assignments were made for this project.")
                    else:
                        for role, assigned_workers in project_assignments.items():
                            role_hours = specific_role_hours.get(role, default_role_hours)

                            if not isinstance(assigned_workers, list):
                                assigned_workers = [assigned_workers]

                            worker_display = ", ".join(str(worker) for worker in assigned_workers)
                            st.write(
                                f"**{role}:** {worker_display} — "
                                f"{role_hours} hours/week each "
                                f"({role_hours * len(assigned_workers)} total hours/week)"
                            )

            st.divider()


            # -----------------------------
            # BUILD DETAILED DATA TABLES
            # -----------------------------

            # Deadline details table.
            selected_project_deadline_rows = []

            for project in selected_projects:
                selected_project_deadline_rows.append({
                    "Project": project,
                    "Input Priority": projects_data[project].get("priority", ""),
                    "Deadline Urgency": projects_data[project].get("deadline_urgency", 0),
                    "Total Priority": projects_data[project].get(
                        "effective_priority",
                        projects_data[project].get("priority", "")
                    ),
                    "Weeks Until Due": projects_data[project].get("weeks_until_due", ""),
                    "Duration Weeks": projects_data[project].get("estimated_duration_weeks", 1),
                    "Deadline-Valid Start Weeks": ", ".join(
                        str(week)
                        for week in projects_data[project].get("valid_start_weeks", [])
                    )
                })


            # Project relationship rules table.
            relationship_rows = []

            for project_name, project_data in projects_data.items():
                depends_on = []
                conflicts_with = []

                for dependent_project, required_project in project_dependencies:
                    if dependent_project == project_name:
                        depends_on.append(required_project)

                for project_a, project_b in project_conflicts:
                    if project_a == project_name:
                        conflicts_with.append(project_b)
                    elif project_b == project_name:
                        conflicts_with.append(project_a)

                relationship_rows.append({
                    "Project": project_name,
                    "Depends On": ", ".join(depends_on) if depends_on else "None",
                    "Conflicts With": ", ".join(conflicts_with) if conflicts_with else "None",
                    "Mandatory": "Yes" if project_name in mandatory_projects else "No"
                })


            # -----------------------------
            # EXPORT RESULTS
            # -----------------------------

            summary_rows = helper.build_summary_rows(
                total_selected_projects=total_selected_projects,
                total_entered_projects=total_entered_projects,
                total_assignments=total_assignments,
                total_required_roles_for_selected_projects=total_required_roles_for_selected_projects,
                objective_score=objective_score
            )

            settings_rows = helper.build_settings_rows(
                min_suitability=st.session_state.min_suitability_input,
                completion_bonus_weight=st.session_state.completion_bonus_input,
                preference_bonus_weight=st.session_state.preference_bonus_input,
                priority_bonus_weight=st.session_state.priority_bonus_input,
                start_week_penalty_weight=st.session_state.start_week_penalty_input
            )

            excel_file = helper.create_results(
                summary_rows=summary_rows,
                settings_rows=settings_rows,
                schedule_rows=main_results_rows,
                assignment_rows=assignment_rows,
                unselected_rows=unselected_project_explanations,
                workload_rows=weekly_hours_usage_rows,
                deadline_rows=selected_project_deadline_rows,
                relationship_rows=relationship_rows
            )

            with export_placeholder.container():

                st.markdown("### Export Results")

                st.download_button(
                    label="Download Results (Excel)",
                    data=excel_file,
                    file_name="Optimization_Results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    on_click="ignore"
                )

            # -----------------------------
            # TECHNICAL DETAILS
            # -----------------------------
            with st.expander("View detailed optimization data"):
                st.caption(
                    "These tables provide the more technical details behind the result. "
                    "They are hidden by default to keep the main results easier to read."
                )

                st.markdown("#### Full Role Assignment Table")

                if len(assignment_rows) > 0:
                    st.dataframe(assignment_rows, use_container_width=True, hide_index=True)
                else:
                    st.info("No role assignments were made.")

                st.markdown("#### Worker Weekly Workload")

                if len(weekly_hours_usage_rows) > 0:
                    st.dataframe(weekly_hours_usage_rows, use_container_width=True, hide_index=True)
                else:
                    st.info("No weekly hours were used.")

                st.markdown("#### Deadline Details")
                st.caption(
                    "Deadline-valid start weeks are based on project duration and deadline only. "
                    "Dependencies, conflicts, and worker availability may affect the final chosen schedule."
                )

                if len(selected_project_deadline_rows) > 0:
                    st.dataframe(selected_project_deadline_rows, use_container_width=True, hide_index=True)
                else:
                    st.info("No deadline details available.")

                st.markdown("#### Project Relationship Rules")
                st.caption(
                    "Dependencies require one project to be scheduled after another. "
                    "Conflicts prevent projects from being active in the same week. "
                    "Mandatory projects must be selected if the model is feasible."
                )

                if len(relationship_rows) > 0:
                    st.dataframe(relationship_rows, use_container_width=True, hide_index=True)
                else:
                    st.info("No project relationship rules were entered.")

    st.button(
                "Continue to Feedback",
                on_click=go_to_page,
                args=("Feedback",),
            )


# -----------------------------
# FEEDBACK TAB
# -----------------------------

if active_page == "Feedback":
    st.subheader("Feedback")

    st.write(
        "Please complete this short feedback form after using the optimizer. This will help improve the tool in the future. Thank you!"
    )

    st.link_button(
        "Open Feedback Form",
        "https://forms.cloud.microsoft/Pages/ResponsePage.aspx?id=2IYwsWuZZUCLY3hqklhgtb2d2tjnpZlPoLqIluS3j7tURjFQT0NHWjRaQUZLM1BTRkZSWFVEVDA1Ri4u",
        use_container_width=True
    )
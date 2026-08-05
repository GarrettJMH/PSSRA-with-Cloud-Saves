import streamlit as st
from datetime import date

import scenario_file_helpers as scenario_files
import cloud_save_helpers as cloud_save


DEFAULTS = {
    "completion_bonus_input": 0.25,
    "preference_bonus_input": 0.20,
    "priority_bonus_input": 0.50,
    "start_week_penalty_input": 0.01
}


def is_user_logged_in():
    """
    Safely checks whether the user is logged in.
    Returns False if Streamlit auth is not configured.
    """

    return bool(getattr(st.user, "is_logged_in", False))


def streamlit_auth_is_configured():
    """
    Checks whether Streamlit login appears to be configured in secrets.
    """

    try:
        auth_config = st.secrets.get("auth", {})
    except Exception:
        return False

    required_keys = [
        "redirect_uri",
        "cookie_secret",
        "client_id",
        "client_secret",
        "server_metadata_url",
    ]

    return all(
        str(auth_config.get(key, "")).strip() != ""
        for key in required_keys
    )


def handle_login_choice():
    """
    Lets users either log in for autosave or continue as a guest.
    If Streamlit auth is not configured, the app still allows guest mode.
    """

    if "guest_mode" not in st.session_state:
        st.session_state.guest_mode = False

    if is_user_logged_in():
        st.session_state.guest_mode = False
        return

    if st.session_state.guest_mode:
        return

    st.title("PSSRA Optimizer")

    st.info(
        "Log in to enable cloud autosave and restore your previous work after refreshing the page."
    )

    if not streamlit_auth_is_configured():
        st.warning(
            "Login is not configured yet for this deployment. "
            "You can continue without logging in, but autosave and refresh recovery will be disabled."
        )

        if st.button("Continue without autosave", use_container_width=True):
            st.session_state.guest_mode = True
            st.rerun()

        st.stop()

    st.warning(
        "You can continue without logging in, but autosave and refresh recovery will be disabled. "
        "Use the scenario download option if you want to save your work manually."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Log in", use_container_width=True):
            st.login()

    with col2:
        if st.button("Continue without logging in", use_container_width=True):
            st.session_state.guest_mode = True
            st.rerun()

    st.stop()


def initialize_session_state():
    """
    Initializes project, worker, Q-matrix, editor version, and default setting state.
    """

    if "projects" not in st.session_state:
        st.session_state.projects = []

    if "workers" not in st.session_state:
        st.session_state.workers = []

    if "q_matrix" not in st.session_state:
        st.session_state.q_matrix = []

    if "projects_editor_version" not in st.session_state:
        st.session_state.projects_editor_version = 0

    if "workers_editor_version" not in st.session_state:
        st.session_state.workers_editor_version = 0

    if "q_matrix_editor_version" not in st.session_state:
        st.session_state.q_matrix_editor_version = 0

    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)


def reset_weights_to_default():
    for key, value in DEFAULTS.items():
        st.session_state[key] = value


def set_scenario_file_message(message, message_type="success"):
    st.session_state.scenario_file_message = message
    st.session_state.scenario_file_message_type = message_type


def set_cloud_save_message(message, message_type="success"):
    st.session_state.cloud_save_message = message
    st.session_state.cloud_save_message_type = message_type


def get_current_settings():
    return {
        "start_date_input": str(st.session_state.start_date_input),
        "min_suitability_input": st.session_state.min_suitability_input,
        "completion_bonus_input": st.session_state.completion_bonus_input,
        "preference_bonus_input": st.session_state.preference_bonus_input,
        "priority_bonus_input": st.session_state.priority_bonus_input,
        "start_week_penalty_input": st.session_state.start_week_penalty_input,
    }


def current_app_has_content():
    return (
        len(st.session_state.projects) > 0
        or len(st.session_state.workers) > 0
        or len(st.session_state.q_matrix) > 0
    )


def get_logged_in_user_id():
    if hasattr(st.user, "sub") and st.user.sub:
        return str(st.user.sub)

    if hasattr(st.user, "email") and st.user.email:
        return str(st.user.email)

    return ""


def get_logged_in_user_email():
    if hasattr(st.user, "email") and st.user.email:
        return str(st.user.email)

    return ""


def autosave_current_state(reason="", delete_if_empty=False):
    """
    Saves the current app state as the logged-in user's latest autosave.
    This overwrites the previous autosave for that user.
    """

    if not is_user_logged_in():
        return

    if not current_app_has_content():
        if delete_if_empty:
            try:
                cloud_save.delete_user_autosave(get_logged_in_user_id())
                st.session_state.autosave_status_message = "Autosave cleared."
                st.session_state.autosave_status_type = "success"
            except Exception as error:
                st.session_state.autosave_status_message = f"Autosave clear failed: {error}"
                st.session_state.autosave_status_type = "error"
        return

    try:
        scenario_data = scenario_files.build_scenario_dictionary(
            scenario_name="Autosave",
            projects=st.session_state.projects,
            workers=st.session_state.workers,
            q_matrix=st.session_state.q_matrix,
            settings=get_current_settings()
        )

        cloud_save.save_user_autosave(
            user_id=get_logged_in_user_id(),
            user_email=get_logged_in_user_email(),
            scenario_json=scenario_data
        )

        st.session_state.autosave_status_message = "Autosaved."
        st.session_state.autosave_status_type = "success"

    except Exception as error:
        st.session_state.autosave_status_message = f"Autosave failed: {error}"
        st.session_state.autosave_status_type = "error"


def apply_scenario_data_to_app(scenario_data):
    """
    Applies loaded scenario data to Streamlit session state.
    """

    st.session_state.projects = scenario_data.get("projects", [])
    st.session_state.workers = scenario_data.get("workers", [])
    st.session_state.q_matrix = scenario_data.get("q_matrix", [])

    settings = scenario_data.get("settings", {})

    if "start_date_input" in settings:
        try:
            st.session_state.start_date_input = date.fromisoformat(
                str(settings["start_date_input"])
            )
        except ValueError:
            pass

    for key in [
        "min_suitability_input",
        "completion_bonus_input",
        "preference_bonus_input",
        "priority_bonus_input",
        "start_week_penalty_input",
    ]:
        if key in settings:
            try:
                st.session_state[key] = float(settings[key])
            except (TypeError, ValueError):
                pass

    st.session_state.projects_editor_version += 1
    st.session_state.workers_editor_version += 1
    st.session_state.q_matrix_editor_version += 1


def load_scenario_from_uploaded_file():
    """
    Loads projects, workers, Q matrix, and settings from an uploaded JSON scenario file.
    """

    uploaded_file = st.session_state.get("scenario_file_upload")

    try:
        scenario_data = scenario_files.read_uploaded_scenario_file(uploaded_file)
    except ValueError as error:
        set_scenario_file_message(str(error), "error")
        return

    apply_scenario_data_to_app(scenario_data)

    set_scenario_file_message("Scenario file loaded.", "success")
    autosave_current_state(reason="scenario file loaded")


def restore_autosave_before_widgets():
    """
    Restores the logged-in user's autosave once per session, before widgets are created.
    """

    if (
        is_user_logged_in()
        and "autosave_restore_checked" not in st.session_state
    ):
        st.session_state.autosave_restore_checked = True

        try:
            autosave_row = cloud_save.load_user_autosave(get_logged_in_user_id())

            if autosave_row is not None:
                scenario_data = autosave_row.get("scenario_json")

                if scenario_data is not None:
                    st.session_state.pending_scenario_to_apply = scenario_data
                    st.session_state.pending_scenario_message = (
                        "Recovered your previous autosaved work."
                    )

        except Exception as error:
            st.session_state.autosave_status_message = (
                f"Autosave restore unavailable: {error}"
            )
            st.session_state.autosave_status_type = "warning"

    if "pending_scenario_to_apply" in st.session_state:
        scenario_data = st.session_state.pop("pending_scenario_to_apply")

        apply_scenario_data_to_app(scenario_data)

        pending_message = st.session_state.pop(
            "pending_scenario_message",
            "Scenario loaded."
        )

        st.session_state.autosave_status_message = pending_message
        st.session_state.autosave_status_type = "success"
        st.session_state.autosave_after_widgets_created = True
        st.session_state.autosave_after_widgets_message = pending_message


def clear_all_app_data():
    """
    Clears all project, worker, and Q-matrix data from the app
    and deletes the logged-in user's autosave recovery state.
    """

    st.session_state.projects = []
    st.session_state.workers = []
    st.session_state.q_matrix = []

    st.session_state.projects_editor_version += 1
    st.session_state.workers_editor_version += 1
    st.session_state.q_matrix_editor_version += 1

    if "q_project_filter" in st.session_state:
        del st.session_state.q_project_filter

    if "cloud_saved_scenarios" in st.session_state:
        st.session_state.cloud_saved_scenarios = []

    if is_user_logged_in():
        try:
            cloud_save.delete_user_autosave(get_logged_in_user_id())
            st.session_state.autosave_status_message = "All data cleared and autosave deleted."
            st.session_state.autosave_status_type = "success"
        except Exception as error:
            st.session_state.autosave_status_message = f"Data cleared, but autosave delete failed: {error}"
            st.session_state.autosave_status_type = "error"
    else:
        st.session_state.autosave_status_message = "All local session data cleared."
        st.session_state.autosave_status_type = "success"
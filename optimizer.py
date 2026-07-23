# Project selection, scheduling, and role assignment model.
# This file contains only the optimization logic.
# The Streamlit app prepares the input dictionaries and displays the results.

# Import PuLP for linear/integer optimization.
import pulp

# Class representing the optimization model.
class ProjectSelectionGMRA:

    # Store all input data passed from Streamlit.
    def __init__(self, workers, projects, Q, project_dependencies=None, project_conflicts=None,
                 mandatory_projects=None, weekly_hours=None, worker_preferences=None, worker_unavailability=None,
                  worker_weekly_capacity=None, min_suitability=0.3, alpha=0.25, beta=0.2, gamma=0.01, delta=0.5):

        # List of available workers.
        self.workers = workers

        # Dictionary of projects and their details.
        self.projects = projects

        # Nested Q matrix where Q[worker][project][role] gives the suitability score.
        self.Q = Q

        # Project dependency constraints.
        self.project_dependencies = project_dependencies if project_dependencies is not None else []

        # Project conflict constraints
        self.project_conflicts = project_conflicts if project_conflicts is not None else []

        # Projects that must be selected if the model remains feasible.
        self.mandatory_projects = mandatory_projects if mandatory_projects is not None else []

        # Weekly available project hours for each worker.
        self.weekly_hours = weekly_hours if weekly_hours is not None else {}

        # Worker preferences
        self.worker_preferences = worker_preferences if worker_preferences is not None else {}

        # Worker unavailability information
        self.worker_unavailability = worker_unavailability if worker_unavailability is not None else {}

        # Weekly capacity for each worker in each week.
        self.worker_weekly_capacity = worker_weekly_capacity if worker_weekly_capacity is not None else {}

        # Minimum Q score required for a worker to be eligible.
        self.min_suitability = min_suitability

        # Weights for the objective function components.
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.delta = delta


    # Build and solve the optimization problem.
    def resolve(self):

        # Create a maximization problem.
        model = pulp.LpProblem("University_Dept_Project_Selection_&_Role_Assignment", pulp.LpMaximize)

        # Create local lists for workers and projects.
        worker_list = self.workers
        project_list = list(self.projects.keys())

        T_pr = {} # Matrix of workers needed for roles r in project p

        H_pr = {} # Weekly hours required for role r in project p

        A_iw = {} # Hours workers i is available in week w

        C_pq = {} # Matrix for conflicts between two projects

        D_pq = {} # Matrix for dependencies between two projects

        Q_ipr = {}

        # Create each required project-role.
        required_roles = [
            (project, role)
            for project in project_list
            for role in self.projects[project]["required_roles"]
        ]

        # Need 1 worker for each role in each project
        for project, role, in required_roles:
            T_pr[(project, role)] = self.projects[project].get("role_requirements", {}).get(role, 1)

        for p in project_list:
            for q in project_list:
                C_pq[(p, q)] = 0
                D_pq[(p, q)] = 0
        
        for p1, p2 in self.project_conflicts:
                C_pq[(p1, p2)] = 1
                C_pq[(p2, p1)] = 1

        for dependent_project, required_project in self.project_dependencies:
            D_pq[(dependent_project, required_project)] = 1

        # Create every possible worker-project-role assignment considered by the solver.
        assignment_keys = [
            (worker, project, role)
            for worker in worker_list
            for project, role in required_roles
        ]

        # Binary project-selection variables.
        # selected_project[project] = 1 if the project is selected, 0 otherwise.
        selected_project = pulp.LpVariable.dicts(
            "Selected_Project",
            project_list,
            0,
            1,
            pulp.LpInteger
        )

        # Binary worker-assignment variables.
        # assignment[worker, project, role] = 1 if the worker is assigned to that project-role.
        assignment = pulp.LpVariable.dicts(
            "Assignment",
            assignment_keys,
            0,
            1,
            pulp.LpInteger
        )

        # Start-week keys for each project and each valid start week.
        start_keys = [
            (project, week)
            for project in project_list
            for week in sorted(set(self.projects[project].get("valid_start_weeks", [1])))
        ]

        # Binary project-start variables.
        # start_project[project, week] = 1 if the selected project starts in that week.
        start_project = pulp.LpVariable.dicts(
            "Start_Project",
            start_keys,
            0,
            1,
            pulp.LpInteger
        )

        # Combine the worker assignment with a possible project start week.
        scheduled_assignment_keys = [
            (worker, project, role, week)
            for worker in worker_list
            for project, role in required_roles
            for week in self.projects[project].get("valid_start_weeks", [1])
        ]

        for worker, project, role in assignment_keys:
            Q_ipr[(worker, project, role)] = self.Q[worker][project][role]

        # Binary scheduled-assignment variables.
        # scheduled_assignment[worker, project, role, week] = 1 only when worker is assigned & project starts that week.
        scheduled_assignment = pulp.LpVariable.dicts(
            "Scheduled_Assignment",
            scheduled_assignment_keys,
            0,
            1,
            pulp.LpInteger
        )

        # -----------------------------
        # OBJECTIVE FUNCTION COMPONENTS
        # -----------------------------

        # Project value rewards selecting higher-priority or deadline-adjusted projects.
        project_value = pulp.lpSum([
            self.projects[project].get("effective_priority", self.projects[project]["priority"])
            * selected_project[project]
            for project in project_list
        ])


        # Assignment quality rewards assigning workers to project roles where they have higher Q scores.
        assignment_quality = pulp.lpSum(
            Q_ipr[(worker, project, role)] / len(self.projects[project]["required_roles"])
            * assignment[(worker, project, role)]
            for worker, project, role in assignment_keys
        )


        # Small bonus to assigning workers to preferred roles.
        preference_bonus = pulp.lpSum(
            1 * assignment[(worker, project, role)]
            for worker, project, role, in assignment_keys
                if role in self.worker_preferences.get(worker, [])
        )


        # The later the chosen start week, the larger the penalty.
        start_week_penalty = pulp.lpSum(
            week * start_project[(project, week)]
            for project in project_list
            for week in self.projects[project].get("valid_start_weeks", [1])
        )


        # Bonus for completing projects
        project_completion_bonus = pulp.lpSum(
            selected_project[project] for project in project_list
        )

        # Main objective function:
        # maximize project value and worker-role fit, while slightly preferring earlier start weeks.
        model += (assignment_quality + (self.delta * project_value) + (self.beta * preference_bonus) + (self.alpha * project_completion_bonus) - (self.gamma * start_week_penalty))

        # -----------------------------
        # PROJECT SELECTION AND ROLE-FILLING CONSTRAINTS
        # -----------------------------

        # If a project is selected, each required role must be filled by exactly one worker.
        for project in project_list:
            for role in self.projects[project]["required_roles"]:
                model += (
                    pulp.lpSum(assignment[(worker, project, role)] for worker in worker_list)
                    == T_pr[(project, role)] * selected_project[project],
                    f"Fill_{project}_{role}"
                )

        # Force mandatory projects to be selected.
        for project in self.mandatory_projects:
            model += (
                selected_project[project] == 1,
                f"Mandatory_{project}"
            )

        # Prevent projects from being selected if they cannot finish before their deadline.
        for project in project_list:
            if self.projects[project].get("deadline_feasible", True) is False:
                model += (
                    selected_project[project] == 0,
                    f"Deadline_Infeasible_{project}"
                )

        # If a project is selected, choose exactly one valid start week.
        for project in project_list:
            valid_start_weeks = sorted(set(self.projects[project].get("valid_start_weeks", [1])))

            # Safety fallback in case a project has no valid start weeks stored.
            if not valid_start_weeks:
                valid_start_weeks = [1]

            model += (
                pulp.lpSum(start_project[(project, week)] for week in valid_start_weeks)
                == selected_project[project],
                f"StartWeek_Selected_{project}"
            )

        # -----------------------------
        # PROJECT START-WEEK EXPRESSIONS
        # -----------------------------

        # Converts each project's chosen start week into a numeric expression.
        project_start_week = {}

        for project in project_list:
            project_start_week[project] = pulp.lpSum(
                week * start_project[(project, week)]
                for week in self.projects[project].get("valid_start_weeks", [1])
                )

        # -----------------------------
        # DEPENDENCY CONSTRAINTS
        # -----------------------------

        for p in project_list:
                for q in project_list:
                    if D_pq[(p, q)] ==1:
                        model += (
                            selected_project[p] <= selected_project[q],
                            f"Dependency_{p}_requires_{q}"
                        )

        # If the dependent project is selected, it must start after the required project finishes.
        # If the dependent project is not selected, the large M value relaxes the constraint.
        big_m = 100

        for p in project_list:
                for q in project_list:
                    if D_pq[(p, q)] == 1:
                        required_duration = self.projects[q].get("estimated_duration_weeks", 1)

                        model += (
                            project_start_week[p]
                            >= project_start_week[q]
                            + required_duration
                            - big_m * (1 - selected_project[p]),
                            f"Schedule_Dependency_{p}_after_{q}"
                        )

        # -----------------------------
        # SCHEDULED ASSIGNMENT LINKING
        # -----------------------------

        # Link scheduled assignments to worker-role assignments and chosen project start weeks.
        # scheduled_assignment = 1 only when both assignment = 1 and start_project = 1.
        for worker, project, role, start_week in scheduled_assignment_keys:

            # A scheduled assignment can only exist if the worker is assigned to that project-role.
            model += (
                scheduled_assignment[(worker, project, role, start_week)]
                <= assignment[(worker, project, role)],
                f"Scheduled_Assignment_Uses_Assignment_{worker}_{project}_{role}_{start_week}"
            )

            # A scheduled assignment can only exist if the project starts in that start week.
            model += (
                scheduled_assignment[(worker, project, role, start_week)]
                <= start_project[(project, start_week)],
                f"Scheduled_Assignment_Uses_Start_{worker}_{project}_{role}_{start_week}"
            )

            # If the worker is assigned and the project starts in this week, scheduled-assignment variable must become 1.
            model += (
                scheduled_assignment[(worker, project, role, start_week)]
                >= assignment[(worker, project, role)] + start_project[(project, start_week)] - 1,
                f"Scheduled_Assignment_Link_{worker}_{project}_{role}_{start_week}"
            )

        # Build the set of all weeks that could be active based on possible project schedules.
        all_weeks = sorted({
            active_week
            for project in project_list
            for start_week in self.projects[project].get("valid_start_weeks", [1])
            for active_week in range(
                start_week,
                start_week + self.projects[project].get("estimated_duration_weeks", 1)
            )
        })

        #######################
        # MATRIX HELPER

        for worker in worker_list:
            for week in all_weeks:
                if week in self.worker_unavailability.get(worker, []):
                    A_iw[(worker, week)] = 0
                
                else:
                    A_iw[(worker, week)] = (
                        self.worker_weekly_capacity.get(worker, {}).get(week, self.weekly_hours.get(worker, 0))
                    )

        ##########################

        # -----------------------------
        # ROLE-SPECIFIC HOURS HELPER
        # -----------------------------

        def get_role_hours(project, role):
            """
            Gets the weekly hours for a specific project role.
            If role-specific hours exist, use those.
            Otherwise, fall back to the project's general role hours/week value.
            """

            specific_role_hours = self.projects[project].get("specific_role_hours", {})

            return specific_role_hours.get(
                role,
                self.projects[project].get("role_hours_per_week", 1)
        )

        #######################
        #MATRIX HOURS HELPER

        for project, role in required_roles:
            H_pr[(project, role)] = get_role_hours(project, role)

        #################

        # -----------------------------
        # CONFLICT CONSTRAINTS
        # -----------------------------

        # Conflicting projects are allowed to both be selected, but they cannot be active during the same week.      
        for p in project_list:
            for q in project_list:
                if p < q and C_pq[(p, q)] == 1:
                    for week in all_weeks:
                        
                        p_active = pulp.lpSum(
                            start_project[(p, start_week)]
                            for start_week in self.projects[p].get("valid_start_weeks", [1])
                            if start_week <= week < start_week + self.projects[p].get("estimated_duration_weeks", 1)
                        )

                        q_active = pulp.lpSum(
                            start_project[(q, start_week)]
                            for start_week in self.projects[q].get("valid_start_weeks", [1])
                            if start_week <= week < start_week + self.projects[q].get("estimated_duration_weeks", 1)
                        )

                        model += (
                            p_active + q_active <= 1,
                            f"No_Overlap_Between_{p}_{q}_Week_{week}"
                        )


        # -----------------------------
        # WEEKLY WORKER-HOUR CONSTRAINTS
        # -----------------------------

        # For each worker and each possible active week, sum the hours from all scheduled assignments
        # active in that week and ensure the total does not exceed the worker's weekly available hours.
        for worker in worker_list:
            for week in all_weeks:
                active_hours_this_week = pulp.lpSum(
                    H_pr[(project, role)]
                    * scheduled_assignment[(worker, project, role, start_week)]
                    for project, role in required_roles
                    for start_week in self.projects[project].get("valid_start_weeks", [1])
                    if start_week <= week < start_week + self.projects[project].get("estimated_duration_weeks", 1)
                )

                model += (
                    active_hours_this_week <= A_iw[(worker, week)],
                    f"Weekly_Hours_Capacity_{worker}_Week_{week}"
                )

        # -----------------------------
        # SUITABILITY THRESHOLD CONSTRAINTS
        # -----------------------------

        # Prevent assignments where the worker's Q score is below the minimum suitability threshold.
        for worker, project, role in assignment_keys:
            if Q_ipr[(worker, project, role)] < self.min_suitability:
                model += (
                    assignment[(worker, project, role)] == 0,
                    f"Unsuitable_{worker}_{project}_{role}"
                )

        # -----------------------------
        # SOLVE MODEL
        # -----------------------------

        # Solve the optimization problem using PuLP's CBC solver.
        status = model.solve(pulp.PULP_CBC_CMD(msg=False))

        # Print the solver status for debugging.
        print("Solver status:", pulp.LpStatus[status])

        # If the solution is not optimal, return empty results using the same structure expected by the app.
        if pulp.LpStatus[status] != "Optimal":
            print("No optimal feasible solution found.")
            return [], {}, None, {}

        # -----------------------------
        # EXTRACT SOLUTION FOR STREAMLIT DISPLAY
        # -----------------------------

        # Prepare containers for solved project list, assignments, and project schedule.
        selected = []
        assignments = {}
        project_schedule = {}

        # Extract selected projects and their chosen schedules from the decision variables.
        for project in project_list:

            # Only process projects that were selected by the optimizer.
            if pulp.value(selected_project[project]) == 1:
                selected.append(project)
                assignments[project] = {}

                # Find the start week chosen by the optimizer.
                chosen_start_week = None

                for week in self.projects[project].get("valid_start_weeks", [1]):
                    if pulp.value(start_project[(project, week)]) == 1:
                        chosen_start_week = week
                        break

                # Convert the chosen start week and duration into scheduled active weeks.
                if chosen_start_week is not None:
                    duration = self.projects[project].get("estimated_duration_weeks", 1)
                    scheduled_active_weeks = list(
                        range(chosen_start_week, chosen_start_week + duration)
                    )
                else:
                    scheduled_active_weeks = []

                # Store schedule information for display in the Streamlit results tab.
                project_schedule[project] = {
                    "Start Week": chosen_start_week,
                    "Scheduled Active Weeks": scheduled_active_weeks
                }

                # Determine which worker was assigned to each required role for this selected project.
                for role in self.projects[project]["required_roles"]:
                    assigned_workers = []

                    for worker in worker_list:
                        if pulp.value(assignment[(worker, project, role)]) == 1:
                            assigned_workers.append(worker)

                    # Store the assigned worker for the current project-role.
                    assignments[project][role] = assigned_workers

        # Calculate the final objective score of the solved optimization model.
        objective_score = pulp.value(model.objective)

        # Return the selected projects, role assignments, objective score, and selected project schedules.
        return selected, assignments, objective_score, project_schedule
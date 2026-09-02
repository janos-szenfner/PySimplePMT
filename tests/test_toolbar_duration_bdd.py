"""
pytest-bdd tests for toolbar duration functionality.

Run with:
    python3 -m pytest tests/test_toolbar_duration_bdd.py -v
"""

from datetime import datetime, timedelta
from pytest_bdd import given, parsers, scenarios, then, when

from gantt_app.models import Task
from gantt_app.utils.mermaid_importer import MermaidImporter
from gantt_app.workdaycalendar import WorkingCalendar


# Load the Gherkin scenarios
scenarios("features/toolbar_duration.feature")


def end_date_for(start: datetime, duration_days: int) -> datetime:
    """The expression the create dialog and the importers both use."""
    return WorkingCalendar().add_working_days(start, duration_days)


# SCENARIO: Created task duration matches the request
@given("a start date of 2024-01-01", target_fixture="start_date")
def start_date():
    return datetime(2024, 1, 1)


@when("creating tasks with various requested durations", target_fixture="created_tasks")
def create_tasks_with_various_durations(start_date):
    tasks = []
    requested_durations = [1, 2, 7, 30, 365]
    for requested in requested_durations:
        task = Task.create_task(
            "T", start_date, end_date_for(start_date, requested)
        )
        tasks.append({'requested': requested, 'task': task})
    return tasks


@then("the task duration should match the requested duration")
def check_task_duration_matches_request(created_tasks):
    for task_dict in created_tasks:
        requested = task_dict['requested']
        task = task_dict['task']
        assert task.duration_days == requested, f"asked for {requested} days"


# SCENARIO: Single day task starts and ends together
@when("creating a task with duration of 1 day", target_fixture="single_day_task")
def create_single_day_task(start_date):
    return Task.create_task("T", start_date, end_date_for(start_date, 1))


@then("the task start_date should equal end_date")
def check_single_day_task_dates(single_day_task):
    assert single_day_task.start_date == single_day_task.end_date


@then("the task duration_days should be 1")
def check_single_day_task_duration(single_day_task):
    assert single_day_task.duration_days == 1


# SCENARIO: Task duration agrees with the mermaid importer
@when("creating tasks and importing tasks with same durations", target_fixture="comparison_tasks")
def create_and_import_tasks(start_date):
    importer = MermaidImporter()
    requested_durations = [1, 5, 14]
    
    tasks = []
    for requested in requested_durations:
        created = Task.create_task(
            "T", start_date, end_date_for(start_date, requested)
        )
        imported = Task.create_task(
            "T", start_date,
            importer._parse_duration(f"{requested}d", start_date)
        )
        tasks.append({'created': created, 'imported': imported, 'requested': requested})
    
    return tasks


@then("the created and imported tasks should have the same end dates")
def check_same_end_dates(comparison_tasks):
    for task_dict in comparison_tasks:
        created = task_dict['created']
        imported = task_dict['imported']
        requested = task_dict['requested']
        assert created.end_date == imported.end_date, f"{requested}d disagrees between UI and import"


@then("the created and imported tasks should have the same duration days")
def check_same_duration_days(comparison_tasks):
    for task_dict in comparison_tasks:
        created = task_dict['created']
        imported = task_dict['imported']
        assert created.duration_days == imported.duration_days


# SCENARIO: Subtask duration matches the request
@when("creating a parent task and subtasks with various durations", target_fixture="subtask_data")
def create_parent_and_subtasks(start_date):
    parent = Task.create_task("Parent", start_date,
                              start_date + timedelta(days=30))
    
    subtasks = []
    requested_durations = [1, 4, 10]
    for requested in requested_durations:
        subtask = Task.create_subtask(
            "Child", parent_task=parent,
            end_date=end_date_for(parent.start_date, requested)
        )
        subtasks.append({'requested': requested, 'subtask': subtask})
    
    return {'parent': parent, 'subtasks': subtasks}


@then("the subtask duration should match the requested duration")
def check_subtask_duration_matches_request(subtask_data):
    for subtask_dict in subtask_data['subtasks']:
        requested = subtask_dict['requested']
        subtask = subtask_dict['subtask']
        assert subtask.duration_days == requested, f"asked for {requested} days"
"""
Tests for the resource assignment tab and its helpers.
"""
import unittest
from datetime import datetime
from types import SimpleNamespace

from gantt_app.models import Task, Project
from gantt_app.resource_model import (
    Resource, ResourceRepository, ResourceType, SchedulePattern, TeamPool,
)
from gantt_app.views.assigntask import (
    _resource_load, _workload_text, TaskResourceTab,
)


def _display_available() -> bool:
    """Whether a usable Tk display is present."""
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = _display_available()


class TestAssignTaskHelpers(unittest.TestCase):
    """Unit tests for the pure helper functions in assigntask.py."""

    def test_resource_load_with_no_memberships(self):
        resource = Resource(
            id="r1", name="Jane Smith",
            resource_type=ResourceType.NAMED, role_type="Dev",
            weekly_capacity_hours=40.0,
            schedule_pattern=SchedulePattern.STANDARD)
        used, capacity = _resource_load(resource)
        self.assertEqual(used, 0.0)
        self.assertEqual(capacity, 40.0)

    def test_resource_load_with_memberships(self):
        resource = Resource(
            id="r1", name="Jane Smith",
            resource_type=ResourceType.NAMED, role_type="Dev",
            weekly_capacity_hours=40.0,
            team_memberships={"team1": 0.5, "team2": 0.25},
            schedule_pattern=SchedulePattern.STANDARD)
        used, capacity = _resource_load(resource)
        self.assertEqual(used, 30.0)  # 0.75 * 40
        self.assertEqual(capacity, 40.0)

    def test_workload_text_flags_overloaded(self):
        resource = Resource(
            id="r1", name="Jane Smith",
            resource_type=ResourceType.NAMED, role_type="Dev",
            weekly_capacity_hours=40.0,
            team_memberships={"team1": 1.5},
            schedule_pattern=SchedulePattern.STANDARD)
        text, colour, pct = _workload_text(resource, [resource])
        self.assertIn("60 / 40 hrs", text)
        self.assertIn("OVERLOADED", text)
        self.assertEqual(pct, 150.0)

    def test_workload_text_flags_available(self):
        resource = Resource(
            id="r1", name="Jane Smith",
            resource_type=ResourceType.NAMED, role_type="Dev",
            weekly_capacity_hours=40.0,
            team_memberships={"team1": 0.5},
            schedule_pattern=SchedulePattern.STANDARD)
        text, colour, pct = _workload_text(resource, [resource])
        self.assertIn("20 / 40 hrs", text)
        self.assertEqual(pct, 50.0)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTaskResourceTab(unittest.TestCase):
    """Widget tests for the Resource tab."""

    def setUp(self):
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

        self.repo = ResourceRepository()
        self.repo.resources["r1"] = Resource(
            id="r1", name="Jane Smith",
            resource_type=ResourceType.NAMED, role_type="Dev",
            weekly_capacity_hours=40.0,
            schedule_pattern=SchedulePattern.STANDARD)
        self.repo.teams["t1"] = TeamPool(
            id="t1", name="Core QA Team",
            schedule_pattern=SchedulePattern.STANDARD,
            is_fixed_capacity=True, fixed_hours=80.0)

        self.project = Project(name="Test Project",
                               resource_repository=self.repo)
        self.task = Task(
            id="001", name="Test Task",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 10),
            resource_assignments=[
                {"resource_id": "r1", "estimated_hours": 8.0,
                 "resource_split": 50.0},
            ])

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_builds_and_round_trips_existing_assignments(self):
        tab = TaskResourceTab(self.root, self.project, self.task)
        tab.update_idletasks()
        self.assertEqual(tab.get_assignments(), self.task.resource_assignments)

    def test_add_and_remove_assignment(self):
        empty_task = Task(
            id="002", name="Empty",
            start_date=datetime(2026, 1, 1))
        tab = TaskResourceTab(self.root, self.project, empty_task)
        tab.update_idletasks()

        tab._on_picked("t1")
        self.assertEqual(len(tab.get_assignments()), 1)
        self.assertEqual(tab.get_assignments()[0]["resource_id"], "t1")

        tab._remove(0)
        self.assertEqual(tab.get_assignments(), [])

    def test_rejects_duplicate_resource(self):
        tab = TaskResourceTab(self.root, self.project, self.task)
        tab.update_idletasks()
        tab._on_picked("r1")
        self.assertEqual(len(tab.get_assignments()), 1)

    def test_dropdown_filters_on_search(self):
        tab = TaskResourceTab(self.root, self.project, self.task)
        tab.update_idletasks()
        tab.search_var.set("Core")
        tab._on_search()
        children = tab.dropdown.tree.get_children()
        self.assertEqual(children, ("t1",))

    def test_enter_selects_first_filtered_resource(self):
        tab = TaskResourceTab(self.root, self.project, self.task)
        tab.update_idletasks()
        tab.search_var.set("Core")
        tab._on_search()
        tab._confirm_first()
        ids = [a["resource_id"] for a in tab.get_assignments()]
        self.assertEqual(ids, ["r1", "t1"])

    def test_effort_field_change_updates_assignment(self):
        tab = TaskResourceTab(self.root, self.project, self.task)
        tab.update_idletasks()
        entry = SimpleNamespace(get=lambda: "300")
        tab._make_updater(0, "estimated_hours", entry)(None)
        self.assertEqual(tab.get_assignments()[0]["estimated_hours"], 300.0)

    def test_split_field_change_updates_assignment(self):
        tab = TaskResourceTab(self.root, self.project, self.task)
        tab.update_idletasks()
        entry = SimpleNamespace(get=lambda: "50")
        tab._make_updater(0, "resource_split", entry)(None)
        self.assertEqual(tab.get_assignments()[0]["resource_split"], 50.0)

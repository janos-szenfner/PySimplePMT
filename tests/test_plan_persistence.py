"""
Tests for what survives a save, an open, and a fresh plan - issues #92/#93.

WHY THIS MODULE EXISTS:
======================
Issue #93 was that opening a file brought back only a subset of the plan that
was saved: the status date, the direction, the deadline, the priority, the
calendars and the grid layout were all left behind because the loader copied
fields one at a time and the list was short. The same partial set was what a
new or closed project kept, mirrored - the old plan's settings leaking into a
plan that had never seen them.

Issue #92 was the other direction: the named calendars and the baseline
slots' names and colours are preferences rather than plan data, but they
lived only inside the file, so they were rebuilt for every project and lost
the moment the program closed. They are now kept in the application's own
settings.json, beside the theme mode and the presets.

The toolbar methods are exercised on a SimpleNamespace stand-in, the same
shape tests/test_toolbar_menus.py uses: the helpers are written against
self.<field> and carry no window state, so a namespace answers them as well
as a Toolbar does.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest import mock

from gantt_app.core.baselines import BaselineManager
from gantt_app.core.calendarregistry import (
    CalendarRegistry, NamedCalendar,
)
from gantt_app.core.models import Project, Task, SCHEDULE_FROM_FINISH
from gantt_app.core.workdaycalendar import WorkingCalendar
from gantt_app.views import preferences, theme
from gantt_app.views.toolbar import Toolbar


MONDAY = datetime(2026, 8, 17)


def _named(calendar_id='sixday', name='Six-Day Week', off=frozenset({6})):
    return NamedCalendar(
        id=calendar_id, name=name,
        calendar=WorkingCalendar(non_working_days=set(off)))


class TestThePlanCalendar(unittest.TestCase):
    """The named calendar the plan itself follows (issue #93)."""

    def test_the_plan_names_nothing_until_told_otherwise(self):
        project = Project(name="P")
        self.assertIsNone(project.calendar_id)
        self.assertIs(project.plan_calendar(), project.calendar)

    def test_a_named_calendar_answers_for_the_plan(self):
        project = Project(name="P")
        named = _named()
        project.calendars = CalendarRegistry([named])
        project.calendar_id = named.id
        self.assertIs(project.plan_calendar(), named.calendar)

    def test_an_unknown_id_falls_back_to_the_plans_own(self):
        project = Project(name="P")
        project.calendar_id = 'long-gone'
        self.assertIs(project.plan_calendar(), project.calendar)

    def test_a_task_with_no_calendar_follows_the_plan(self):
        project = Project(name="P")
        named = _named()
        project.calendars = CalendarRegistry([named])
        project.calendar_id = named.id
        task = Task(id='001', name='T',
                    start_date=MONDAY, end_date=MONDAY)
        project.tasks = [task]
        self.assertIs(project.calendar_for(task), named.calendar)

    def test_a_task_naming_its_own_keeps_it(self):
        project = Project(name="P")
        project.calendars = CalendarRegistry(
            [_named(), _named('always', 'Always', frozenset())])
        project.calendar_id = 'sixday'
        task = Task(id='001', name='T', start_date=MONDAY,
                    end_date=MONDAY, calendar_id='always')
        project.tasks = [task]
        self.assertIs(project.calendar_for(task),
                      project.calendars.get('always').calendar)

    def test_the_choice_survives_a_saved_file(self):
        project = Project(name="P")
        project.calendars = CalendarRegistry([_named()])
        project.calendar_id = 'sixday'
        restored = Project.from_dict(project.to_dict())
        self.assertEqual(restored.calendar_id, 'sixday')
        self.assertIs(restored.plan_calendar(),
                      restored.calendars.get('sixday').calendar)

    def test_a_file_from_before_the_choice_opens_on_the_plans_own(self):
        project = Project.from_dict({'name': 'Old', 'tasks': []})
        self.assertIsNone(project.calendar_id)
        self.assertIs(project.plan_calendar(), project.calendar)

    def test_switching_moves_the_finish_not_the_work(self):
        # A five-day task Mon-Fri under the standard week; a calendar with
        # Friday off makes its finish slide rather than its work shrink.
        project = Project(name="P")
        task = Task(id='001', name='T',
                    start_date=MONDAY,
                    end_date=MONDAY.replace(day=21))  # Fri
        project.tasks = [task]
        friday_off = _named('frioff', 'Friday Off', frozenset({4, 5}))
        project.calendars = CalendarRegistry([friday_off])
        self.assertTrue(project.set_plan_calendar('frioff'))
        # Mon-Thu + Sun = the five days the task still holds.
        self.assertEqual(task.end_date, MONDAY.replace(day=23))
        self.assertFalse(project.set_plan_calendar('frioff'))


class TestTakingOnALoadedProject(unittest.TestCase):
    """_take_on_project_fields must carry every field to_dict saves (#93)."""

    def _loaded_project(self) -> Project:
        project = Project(name="Loaded")
        project.status_date = MONDAY
        project.schedule_from = SCHEDULE_FROM_FINISH
        project.deadline = MONDAY.replace(month=12)
        project.priority = 700
        project.hours_per_day = 6
        project.hidden_grid_columns = ['Label', 'Milestone']
        project.custom_filters = [{'name': 'Late', 'query': 'finish'}]
        project.calendars = CalendarRegistry([_named()])
        project.calendar_id = 'sixday'
        return project

    def _toolbar_stub(self, project: Project) -> SimpleNamespace:
        return SimpleNamespace(project=project)

    def test_every_persisted_field_arrives(self):
        stub = self._toolbar_stub(Project(name="Old"))
        loaded = self._loaded_project()
        Toolbar._take_on_project_fields(stub, loaded)
        self.assertEqual(stub.project.status_date, MONDAY)
        self.assertEqual(stub.project.schedule_from, SCHEDULE_FROM_FINISH)
        self.assertEqual(stub.project.deadline, MONDAY.replace(month=12))
        self.assertEqual(stub.project.priority, 700)
        self.assertEqual(stub.project.hours_per_day, 6)
        self.assertEqual(stub.project.hidden_grid_columns,
                         ['Label', 'Milestone'])
        self.assertEqual(stub.project.custom_filters,
                         loaded.custom_filters)
        self.assertIs(stub.project.calendars, loaded.calendars)
        self.assertEqual(stub.project.calendar_id, 'sixday')

    def test_a_blank_project_keeps_nothing_but_the_library(self):
        stub = self._toolbar_stub(self._loaded_project())
        stub.master = SimpleNamespace(
            calendar_library=CalendarRegistry([_named('lib', 'Library')]))
        stub._take_on_project_fields = MethodType(
            Toolbar._take_on_project_fields, stub)
        Toolbar._blank_project(stub, "New Project")
        self.assertIsNone(stub.project.status_date)
        self.assertEqual(stub.project.schedule_from, 'start')
        self.assertIsNone(stub.project.deadline)
        self.assertIsNone(stub.project.calendar_id)
        self.assertEqual(stub.project.tasks, [])
        # ...except the shared library, which is not the plan's own.
        self.assertIs(stub.project.calendars, stub.master.calendar_library)


class TestTheCalendarLibrary(unittest.TestCase):
    """The named calendars kept centrally rather than per file (#92)."""

    def test_a_files_custom_calendar_is_adopted(self):
        library = CalendarRegistry([])
        loaded = Project(name="P")
        loaded.calendars = CalendarRegistry([_named()])
        stub = SimpleNamespace(project=Project(name="Live"),
                               master=SimpleNamespace(
                                   calendar_library=library))
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(theme, 'settings_directory',
                                   return_value=Path(directory)):
                Toolbar._merge_loaded_calendars(stub, loaded)
                self.assertIn('sixday', library)
                self.assertIs(loaded.calendars, library)
                # And it was written down, not just held in memory.
                saved = json.loads(
                    (Path(directory) / theme.SETTINGS_FILE).read_text())
                self.assertTrue(saved.get('calendars'))

    def test_the_library_wins_an_id_it_already_has(self):
        tuned = _named('sixday', 'Six-Day Week', frozenset({0}))
        library = CalendarRegistry([tuned])
        loaded = Project(name="P")
        loaded.calendars = CalendarRegistry([_named()])
        stub = SimpleNamespace(project=Project(name="Live"),
                               master=SimpleNamespace(
                                   calendar_library=library))
        Toolbar._merge_loaded_calendars(stub, loaded)
        self.assertIs(loaded.calendars.get('sixday').calendar,
                      tuned.calendar)

    def test_without_a_library_the_files_own_stand(self):
        loaded = Project(name="P")
        own = CalendarRegistry([_named()])
        loaded.calendars = own
        stub = SimpleNamespace(project=Project(name="Live"),
                               master=SimpleNamespace())
        Toolbar._merge_loaded_calendars(stub, loaded)
        self.assertIs(loaded.calendars, own)


class TestThePreferenceStore(unittest.TestCase):
    """settings.json read-modify-write, and what a damaged file answers."""

    def _settings(self, directory: Path) -> dict:
        return json.loads(
            (directory / theme.SETTINGS_FILE).read_text())

    def test_the_calendar_library_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            with mock.patch.object(theme, 'settings_directory',
                                   return_value=directory):
                registry = CalendarRegistry([_named()])
                self.assertTrue(
                    preferences.save_calendar_library(registry))
                loaded = preferences.load_calendar_library()
                self.assertEqual([n.id for n in loaded], ['sixday'])

    def test_a_missing_key_is_seeded_from_the_presets(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(theme, 'settings_directory',
                                   return_value=Path(d)):
                self.assertTrue(len(preferences.load_calendar_library()))

    def test_an_empty_library_is_honoured(self):
        # Deleting every named calendar is a choice; it is not the same as
        # the key never having been written.
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            with mock.patch.object(theme, 'settings_directory',
                                   return_value=directory):
                preferences.save_calendar_library(CalendarRegistry([]))
                self.assertEqual(len(preferences.load_calendar_library()),
                                 0)

    def test_baseline_names_and_colours_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            with mock.patch.object(theme, 'settings_directory',
                                   return_value=directory):
                preferences.save_baseline_slot_preferences(
                    {2: {'name': 'Go-Live', 'color': '#ff0000'}})
                manager = BaselineManager()
                self.assertTrue(
                    preferences.apply_baseline_slot_preferences(manager))
                slot = manager.get_slot(2)
                self.assertEqual(slot.display_name, 'Go-Live')
                self.assertEqual(slot.color, '#ff0000')
                # Slots with no stored preference keep their own.
                self.assertEqual(manager.get_slot(3).display_name,
                                 'Baseline 3')

    def test_other_keys_in_the_file_are_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            with mock.patch.object(theme, 'settings_directory',
                                   return_value=directory):
                theme.save_mode('dark')
                preferences.save_baseline_slot_preferences(
                    {1: {'name': 'First', 'color': ''}})
                preferences.save_calendar_library(CalendarRegistry([]))
                self.assertEqual(
                    self._settings(directory).get('theme_mode'), 'dark')
                self.assertEqual(theme.load_mode(), 'dark')

    def test_duplicate_filter_names_are_made_unique_on_load(self):
        """
        Issue #80: a file written before the name guards can carry two
        filters of a name - they drew as two identical menu rows where
        only the first answered. The repeats are renamed on the way in.
        """
        data = Project(name="P").to_dict()
        data['custom_filters'] = [
            {'name': 'Milestone', 'rules': [
                {'field': 'Type', 'test': 'equals', 'value': 'Task'}]},
            {'name': 'Milestone', 'rules': [
                {'field': 'Progress', 'test': 'equals', 'value': '0'}]},
            {'name': 'Milestone', 'query': 'type = "Phase"'},
        ]
        project = Project.from_dict(data)
        self.assertEqual([d['name'] for d in project.custom_filters],
                         ['Milestone', 'Milestone (2)', 'Milestone (3)'])

    def test_a_filter_named_like_a_built_in_is_renamed_on_take_on(self):
        """
        The other half of #80: a saved filter wearing a built-in's label
        drew a second identical menu row beside it.
        """
        stub = SimpleNamespace(project=Project(name="Old"))
        loaded = Project(name="Loaded")
        loaded.custom_filters = [
            {'name': 'Milestones', 'rules': [
                {'field': 'Progress', 'test': 'equals', 'value': '0'}]}]
        Toolbar._take_on_project_fields(stub, loaded)
        self.assertEqual(stub.project.custom_filters[0]['name'],
                         'Milestones (2)')

    def test_saving_does_not_pop_a_dialog(self):
        """
        Issue #87: the star leaving the title bar is the confirmation a
        save needs - a "saved successfully" popup on top was noise.
        """
        import gantt_app.views.toolbar as toolbar_mod

        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "p.json")
            stub = SimpleNamespace(project=Project(name="P"),
                                   baseline_manager=None,
                                   current_file_path=None,
                                   master=SimpleNamespace())
            calls = []
            with mock.patch.object(toolbar_mod.messagebox, 'showinfo',
                                   lambda *a, **k: calls.append(a)):
                Toolbar._write_project(stub, path)

            self.assertEqual(calls, [])
            self.assertEqual(stub.current_file_path, path)
            self.assertTrue(Path(path).exists())

    def test_a_damaged_file_is_not_worth_failing_over(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            (directory / theme.SETTINGS_FILE).write_text('{not json')
            with mock.patch.object(theme, 'settings_directory',
                                   return_value=directory):
                self.assertTrue(len(preferences.load_calendar_library()))
                manager = BaselineManager()
                self.assertFalse(
                    preferences.apply_baseline_slot_preferences(manager))


class TestTheFileNameAndTheProjectName(unittest.TestCase):
    """
    Issue #91: how the project name and the file name keep up with each
    other. A file name suggested by the project name is derived, and a
    rename in settings moves the save to a file of the new name. A file
    name the user picked - in Save As, or by opening a file - is locked:
    renames leave it where it is. And a plan never deliberately named
    adopts the first file name it is saved to.
    """

    def _saver(self, project: Project, path=None, locked=False):
        stub = SimpleNamespace(project=project,
                               baseline_manager=None,
                               current_file_path=path,
                               _file_name_locked=locked,
                               task_list=None,
                               master=SimpleNamespace())
        for method in ('_write_project', 'save_project', 'save_project_as',
                       '_report'):
            setattr(stub, method,
                    MethodType(getattr(Toolbar, method), stub))
        return stub

    def _save_as(self, stub, file_path):
        import gantt_app.views.toolbar as toolbar_mod

        with mock.patch.object(toolbar_mod.filedialog,
                               'asksaveasfilename',
                               return_value=file_path):
            Toolbar.save_project_as(stub)

    def test_the_suggestion_writes_spaces_and_unsafe_chars_as_underscores(self):
        from gantt_app.views.toolbar import _file_name_for

        self.assertEqual(_file_name_for('My Plan'), 'My_Plan')
        self.assertEqual(_file_name_for('My Plan: v2/a'), 'My_Plan__v2_a')
        self.assertEqual(_file_name_for('   '), 'untitled')

    def test_save_as_adopts_the_chosen_name_on_an_untouched_plan(self):
        project = Project(name="New Project")
        self.assertFalse(project.name_was_set)
        stub = self._saver(project)
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "my plan_v2.json")
            self._save_as(stub, path)
            self.assertEqual(project.name, 'my plan_v2')
            self.assertTrue(stub._file_name_locked)
            self.assertEqual(stub.current_file_path, path)
            self.assertTrue(Path(path).exists())
            # The adopted name is in the file, not just the live plan.
            self.assertEqual(json.loads(Path(path).read_text())['name'],
                             'my plan_v2')

    def test_save_as_keeps_a_name_the_user_deliberately_set(self):
        project = Project(name="Real Name", name_was_set=True)
        stub = self._saver(project)
        with tempfile.TemporaryDirectory() as d:
            self._save_as(stub, str(Path(d) / "other.json"))
            self.assertEqual(project.name, 'Real Name')
            self.assertTrue(stub._file_name_locked)

    def test_accepting_the_suggestion_leaves_the_name_derived(self):
        project = Project(name="My Plan", name_was_set=True)
        stub = self._saver(project)
        with tempfile.TemporaryDirectory() as d:
            self._save_as(stub, str(Path(d) / "My_Plan.json"))
            self.assertFalse(stub._file_name_locked)
            self.assertEqual(project.name, 'My Plan')

    def test_a_rename_moves_the_save_while_the_name_is_derived(self):
        project = Project(name="New Name", name_was_set=True)
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "Old_Name.json"
            old.write_text('{}')
            stub = self._saver(project, path=str(old), locked=False)
            Toolbar.save_project(stub)
            new = Path(d) / "New_Name.json"
            self.assertEqual(stub.current_file_path, str(new))
            self.assertTrue(new.exists())
            # The old file is left alone - never silently deleted.
            self.assertTrue(old.exists())
            self.assertFalse(stub._file_name_locked)

    def test_a_rename_leaves_a_chosen_file_name_alone(self):
        project = Project(name="New Name", name_was_set=True)
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "picked.json")
            stub = self._saver(project, path=path, locked=True)
            Toolbar.save_project(stub)
            self.assertEqual(stub.current_file_path, path)
            self.assertTrue(Path(path).exists())
            self.assertFalse((Path(d) / "New_Name.json").exists())

    def test_save_asks_before_landing_on_a_strangers_file(self):
        import gantt_app.views.toolbar as toolbar_mod

        project = Project(name="B", name_was_set=True)
        with tempfile.TemporaryDirectory() as d:
            Path(d, "B.json").write_text('{"someone": "elses"}')
            stub = self._saver(project, path=str(Path(d) / "A.json"),
                               locked=False)
            with mock.patch.object(toolbar_mod.messagebox, 'askyesno',
                                   return_value=False):
                Toolbar.save_project(stub)
            self.assertEqual(stub.current_file_path, str(Path(d) / "A.json"))
            self.assertEqual(Path(d, "B.json").read_text(),
                             '{"someone": "elses"}')
            with mock.patch.object(toolbar_mod.messagebox, 'askyesno',
                                   return_value=True):
                Toolbar.save_project(stub)
            self.assertEqual(stub.current_file_path,
                             str(Path(d) / "B.json"))

    def test_the_flag_survives_a_saved_file(self):
        project = Project(name="P", name_was_set=True)
        self.assertTrue(
            Project.from_dict(project.to_dict()).name_was_set)

    def test_an_old_file_guesses_from_whether_the_name_is_the_placeholder(self):
        untouched = Project.from_dict({'name': 'New Project', 'tasks': []})
        self.assertFalse(untouched.name_was_set)
        named = Project.from_dict({'name': 'Vacation Plan', 'tasks': []})
        self.assertTrue(named.name_was_set)

    def test_take_on_carries_the_flag(self):
        stub = SimpleNamespace(project=Project(name="Old"))
        loaded = Project(name="Loaded", name_was_set=True)
        Toolbar._take_on_project_fields(stub, loaded)
        self.assertTrue(stub.project.name_was_set)


if __name__ == '__main__':
    unittest.main()

"""
Tests for the project dashboard: the arithmetic, the drawing and the switch.

WHY THIS MODULE EXISTS:
======================
The dashboard makes claims about the plan - how far along it is, where the
work sits, how much of it is milestones - and a claim drawn as a picture is
one nobody checks by looking. The arithmetic is separated from the widget for
exactly that reason, and most of what is here needs no display at all.

The drawing is checked too, because the first version of this dashboard drew
nothing whatsoever: it built Plotly figures and loaded them into a tkinterweb
frame, which runs no JavaScript, so the panel came up empty and every test
passed. Counting what actually reached the canvas is what stops that being
possible twice.

DEVELOPMENT NOTES:
------------------
The worked example is the one in the specification: eight rows, one of them
30% done, giving 11.43% overall and an 84/16/0 split by type. Numbers taken
from the specification rather than from the code, so the test can disagree
with the code.
"""

import unittest
from datetime import datetime

from gantt_app.models import Project, Task
from gantt_app.views.project_dashboard import (
    dashboard_rows, duration_by_type, kpi_metrics, weighted_progress,
)


BASE = datetime(2026, 1, 5)

#: The specification's example, as
#: (id, name, type, duration, progress, parent, status).
WORKED_EXAMPLE = (
    ("001", "Project Planning", "Task", 2, 0, None, 'Active'),
    ("002", "Requirements Gathering", "Subtask", 1, 0, "001", 'Active'),
    ("003", "Design Phase", "Task", 5, 0, None, 'Active'),
    ("004", "UI Mockups", "Subtask", 3, 0, "003", 'Active'),
    ("005", "Implementation", "Task", 8, 30, None, 'Active'),
    ("006", "Design Review", "Milestone", 0, 0, None, 'Active'),
    ("007", "Testing", "Task", 3, 0, None, 'Active'),
    ("008", "Deployment", "Task", 3, 0, None, 'Active'),
)


def sample_project(**statuses) -> Project:
    """
    The worked example as a plan.

    PARAMETERS:
    -----------
    **statuses
        Rows to mark as something other than the example says, by id -
        sample_project(t003='Draft').
    """
    project = Project(name="Sample")
    for task_id, name, kind, duration, progress, parent, status \
            in WORKED_EXAMPLE:
        project.add_task(Task(
            id=task_id, name=name, task_type=kind, start_date=BASE,
            end_date=BASE, duration=duration, progress=progress,
            parent_task_id=parent, is_milestone=(kind == 'Milestone'),
            status=statuses.get(f"t{task_id}", status),
        ))
    return project


def _display_available() -> bool:
    """Whether a Tk window can be opened here."""
    try:
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


HAVE_DISPLAY = _display_available()


class TestTheRows(unittest.TestCase):
    """Turning a plan into the flat rows the charts read."""

    def test_a_plan_with_nothing_in_it_gives_nothing(self):
        """
        And no invented tasks.

        The dashboard used to fall back to eight sample rows, so a reader
        who opened it before typing anything was shown a stranger's plan
        under their own project's name.
        """
        self.assertEqual(dashboard_rows(Project(name="Empty")), [])

    def test_no_plan_at_all_gives_nothing(self):
        """The same answer, one step earlier."""
        self.assertEqual(dashboard_rows(None), [])

    def test_a_row_carries_what_the_charts_need(self):
        """Every key the four charts read is on every row."""
        row = dashboard_rows(sample_project())[0]

        for key in ('ID', 'Name', 'Type', 'Status', 'Duration', 'Progress',
                    'Level'):
            self.assertIn(key, row)

    def test_the_level_follows_the_parent(self):
        """A root row is one, and a row inside it is two."""
        levels = {row['ID']: row['Level']
                  for row in dashboard_rows(sample_project())}

        self.assertEqual(levels['001'], 1)
        self.assertEqual(levels['002'], 2)
        self.assertEqual(levels['004'], 2)

    def test_a_ring_of_parents_does_not_hang(self):
        """
        A plan whose parent links form a ring is not supposed to exist,
        and the dashboard is not the place to find out. Walked with a
        seen-set rather than by recursion, which answers with a blown
        stack and a window that will not open.
        """
        project = Project(name="Ring")
        for task_id, parent in (("A", "B"), ("B", "A")):
            project.add_task(Task(id=task_id, name=task_id, task_type="Task",
                                  start_date=BASE, end_date=BASE, duration=1,
                                  parent_task_id=parent))

        levels = {row['ID']: row['Level']
                  for row in dashboard_rows(project)}

        self.assertEqual(set(levels), {"A", "B"})


class TestWeightedProgress(unittest.TestCase):
    """How far along the plan is, as one number."""

    def rows(self):
        """The worked example."""
        return dashboard_rows(sample_project())

    def test_the_specifications_worked_example(self):
        """(8 * 30) / 21 = 11.43%."""
        self.assertAlmostEqual(weighted_progress(self.rows()), 11.43,
                               places=2)

    def test_only_the_top_level_counts(self):
        """
        A sub-task's work is already inside the row that brackets it, so
        counting it again would weigh it twice.
        """
        rows = [
            {'Level': 1, 'Duration': 10, 'Progress': 0, 'Type': 'Task'},
            {'Level': 2, 'Duration': 10, 'Progress': 100, 'Type': 'Subtask'},
        ]

        self.assertEqual(weighted_progress(rows), 0.0)

    def test_length_decides_the_weight(self):
        """A finished one-day row does not make a nine-day plan half done."""
        rows = [
            {'Level': 1, 'Duration': 1, 'Progress': 100, 'Type': 'Task'},
            {'Level': 1, 'Duration': 9, 'Progress': 0, 'Type': 'Task'},
        ]

        self.assertAlmostEqual(weighted_progress(rows), 10.0)

    def test_a_plan_holding_no_days_is_not_a_division(self):
        """Every row a milestone: no duration to divide by."""
        rows = [{'Level': 1, 'Duration': 0, 'Progress': 0,
                 'Type': 'Milestone'}]

        self.assertEqual(weighted_progress(rows), 0.0)


class TestDurationByType(unittest.TestCase):
    """What the donut divides up."""

    def test_the_specifications_worked_example(self):
        """21 days of tasks, 4 of sub-tasks, none of milestones."""
        shares = dict(duration_by_type(dashboard_rows(sample_project())))

        self.assertEqual(shares['Task'], 21)
        self.assertEqual(shares['Subtask'], 4)
        self.assertEqual(shares['Milestone'], 0)

    def test_the_shares_are_what_the_specification_says(self):
        """84%, 16% and nothing, out of 25 days."""
        shares = dict(duration_by_type(dashboard_rows(sample_project())))
        total = sum(shares.values())

        self.assertEqual(total, 25)
        self.assertAlmostEqual(shares['Task'] / total * 100, 84.0)
        self.assertAlmostEqual(shares['Subtask'] / total * 100, 16.0)

    def test_the_order_is_the_models_own(self):
        """
        Or the colours move between two readings of the same plan, and a
        reader who learnt that green means sub-task learns it again.
        """
        order = [kind for kind, _days
                 in duration_by_type(dashboard_rows(sample_project()))]

        self.assertEqual(order, ['Task', 'Subtask', 'Milestone'])

    def test_a_type_nobody_used_is_not_listed(self):
        """A plan with no phases says nothing about phases."""
        kinds = {kind for kind, _days
                 in duration_by_type(dashboard_rows(sample_project()))}

        self.assertNotIn('Phase', kinds)


class TestKPIMetrics(unittest.TestCase):
    """The five numbers in the summary box."""

    def setUp(self):
        """The worked example's figures."""
        self.metrics = kpi_metrics(dashboard_rows(sample_project()))

    def test_the_scope_is_the_top_level_days(self):
        """21 days, which is what the specification says."""
        self.assertEqual(self.metrics['total_scope'], 21)

    def test_every_row_is_counted_as_an_item(self):
        """Eight items, sub-tasks included."""
        self.assertEqual(self.metrics['total_items'], 8)

    def test_the_milestones_are_counted(self):
        """One."""
        self.assertEqual(self.metrics['milestones'], 1)

    def test_the_completion_is_the_weighted_progress(self):
        """The two are the same number and have to stay the same number."""
        rows = dashboard_rows(sample_project())

        self.assertEqual(self.metrics['progress'], weighted_progress(rows))

    def test_a_plan_of_active_rows_is_all_active(self):
        """The shares read the Status field, not the progress."""
        self.assertAlmostEqual(self.metrics['active_share'], 100.0)
        self.assertAlmostEqual(self.metrics['draft_share'], 0.0)

    def test_the_drafts_are_the_rest_of_them(self):
        """Two rows of eight marked Draft is a quarter of the plan."""
        metrics = kpi_metrics(dashboard_rows(
            sample_project(t003='Draft', t004='Draft')))

        self.assertAlmostEqual(metrics['active_share'], 75.0)
        self.assertAlmostEqual(metrics['draft_share'], 25.0)

    def test_the_two_shares_always_come_to_a_hundred(self):
        """
        They are written side by side and read as a pair, so a plan whose
        halves do not meet reads as a fault in the arithmetic - which,
        with two counts rounded separately, it would be.
        """
        for drafts in range(len(WORKED_EXAMPLE) + 1):
            marked = {f"t{row[0]}": 'Draft'
                      for row in WORKED_EXAMPLE[:drafts]}
            metrics = kpi_metrics(dashboard_rows(sample_project(**marked)))

            self.assertAlmostEqual(
                metrics['active_share'] + metrics['draft_share'], 100.0,
                msg=f"{drafts} drafts")

    def test_progress_does_not_decide_the_status(self):
        """
        A row can be Active and untouched, or Draft and half done. The
        share used to count the rows that had progress on them, which is a
        different question and was labelled with this one's answer.
        """
        rows = dashboard_rows(sample_project())
        started = [row for row in rows if row['Progress'] > 0]

        self.assertEqual(len(started), 1)
        self.assertAlmostEqual(self.metrics['active_share'], 100.0)

    def test_an_empty_plan_divides_by_nothing(self):
        """Every figure is zero rather than an exception."""
        metrics = kpi_metrics([])

        self.assertEqual(metrics['total_items'], 0)
        self.assertEqual(metrics['active_share'], 0.0)
        self.assertEqual(metrics['draft_share'], 0.0)
        self.assertEqual(metrics['progress'], 0.0)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestWhatReachesTheCanvas(unittest.TestCase):
    """
    That something is actually drawn.

    WHY THESE EXIST:
    ================
    The dashboard this replaced drew four charts' worth of nothing - Plotly
    figures loaded into a frame that runs no JavaScript - and every test of
    it passed, because they all checked the HTML it generated rather than
    what appeared. These count what is on the canvas.
    """

    def setUp(self):
        """The worked example, drawn at a size a window would give it."""
        import customtkinter as ctk

        from gantt_app.views.project_dashboard import ProjectDashboardFrame

        self.ctk = ctk
        self.opening_mode = str(ctk.get_appearance_mode())
        ctk.set_appearance_mode('light')

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = sample_project()
        self.frame = ProjectDashboardFrame(self.root, self.project)
        self.frame.canvas.configure(width=1200, height=800)
        self.frame.refresh()

    def tearDown(self):
        """Put the appearance back, and close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            self.ctk.set_appearance_mode(self.opening_mode)
        except Exception:
            pass

    def texts(self):
        """Every piece of text on the canvas."""
        canvas = self.frame.canvas
        return [canvas.itemcget(item, 'text') for item in canvas.find_all()
                if canvas.type(item) == 'text']

    def kinds(self):
        """How many canvas items of each kind were drawn."""
        canvas = self.frame.canvas
        counted = {}
        for item in canvas.find_all():
            kind = canvas.type(item)
            counted[kind] = counted.get(kind, 0) + 1
        return counted

    def test_all_four_charts_are_titled(self):
        """The panel is four charts, not one that happened to work."""
        titles = self.texts()

        for expected in ("Task Progress (%)",
                         "Duration Allocation by Task Type (Days)",
                         "Duration per Item (Days)",
                         "Summary"):
            self.assertIn(expected, titles)

    def test_the_bars_and_the_ring_are_actually_drawn(self):
        """Rectangles for the bars, arcs for the ring, lines for the grid."""
        kinds = self.kinds()

        self.assertGreater(kinds.get('rectangle', 0), 4)
        self.assertGreater(kinds.get('arc', 0), 0)
        self.assertGreater(kinds.get('line', 0), 0)

    def test_the_ring_has_a_segment_per_type_that_holds_days(self):
        """A milestone holds no days, so it has no segment - only a key."""
        self.assertEqual(self.kinds().get('arc', 0), 2)

    def test_the_summary_shows_the_numbers(self):
        """The figures a reader came for, not just their captions."""
        texts = self.texts()

        self.assertIn("21 Days", texts)
        self.assertIn("8 Items", texts)
        self.assertIn("1 Milestone", texts)
        self.assertIn("11.43%", texts)

    def test_the_summary_names_every_figure(self):
        """Six lines, each with a caption saying what it counts."""
        texts = self.texts()

        for caption in ("Total Project Scope", "Total Items Tracked",
                        "Milestones Count", "Average Progress",
                        "Active Status", "Draft Status"):
            self.assertIn(caption, texts)

    def test_the_two_status_lines_are_drawn_as_a_pair(self):
        """Both letters, both shares, and the two coming to a hundred."""
        from gantt_app.views.project_dashboard import ProjectDashboardFrame

        frame = ProjectDashboardFrame(
            self.root, sample_project(t003='Draft', t004='Draft'))
        frame.canvas.configure(width=1200, height=800)
        frame.refresh()

        texts = [frame.canvas.itemcget(item, 'text')
                 for item in frame.canvas.find_all()
                 if frame.canvas.type(item) == 'text']

        self.assertIn("75% Active (A)", texts)
        self.assertIn("25% Draft (D)", texts)

    def test_an_empty_plan_says_so_and_invents_nothing(self):
        """No bars, no ring, and none of the old sample task names."""
        from gantt_app.views.project_dashboard import ProjectDashboardFrame

        frame = ProjectDashboardFrame(self.root, Project(name="Empty"))
        frame.canvas.configure(width=1200, height=800)
        frame.refresh()

        texts = [frame.canvas.itemcget(item, 'text')
                 for item in frame.canvas.find_all()
                 if frame.canvas.type(item) == 'text']

        self.assertTrue(any("Nothing to summarise" in text
                            for text in texts), texts)
        self.assertFalse(any("Implementation" in text for text in texts))

    def test_a_new_task_reaches_the_dashboard(self):
        """refresh reads the plan again rather than what it drew last."""
        self.project.add_task(Task(id="009", name="Handover",
                                   task_type="Task", start_date=BASE,
                                   end_date=BASE, duration=4))
        self.frame.refresh()

        self.assertIn("25 Days", self.texts())

    def test_the_drawing_follows_the_appearance(self):
        """
        Every colour on a canvas is written into the item that carries it,
        so nothing here follows a theme change until it is drawn again.
        """
        from gantt_app import theme

        light = self.frame.canvas.cget('background')
        self.ctk.set_appearance_mode('dark')
        self.frame.apply_theme()
        dark = self.frame.canvas.cget('background')

        self.assertEqual(str(light), theme.DASH_BOARD_BG[0])
        self.assertEqual(str(dark), theme.DASH_BOARD_BG[1])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestSwitchingBetweenTheTwoCharts(unittest.TestCase):
    """
    View > Charts, which swaps what the right-hand pane holds.

    WHY THESE EXIST:
    ================
    ttk's panes() answers with Tk pathnames rather than widgets, so the
    comparisons that decided what was on screen were all False: choosing
    Dashboard left the chart where it was and added a third pane beside it,
    and choosing Gantt Chart afterwards did nothing at all.
    """

    def setUp(self):
        """A toolbar, a paned window and the two things it can hold."""
        import tkinter as tk
        from tkinter import ttk

        import customtkinter as ctk

        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()
        self.project = sample_project()

        self.toolbar = Toolbar(self.root, self.project)
        self.panes = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.task_list_pane = ctk.CTkFrame(self.panes)
        self.chart = ctk.CTkFrame(self.panes)
        self.panes.add(self.task_list_pane, weight=1)
        self.panes.add(self.chart, weight=3)

        self.toolbar.set_gantt_chart(self.chart)
        self.toolbar.set_content_panes(self.panes)
        self.toolbar.set_dashboard_factory(self._make_dashboard)
        self.built = 0
        self.root.update_idletasks()

    def _make_dashboard(self):
        """What the toolbar calls the first time the dashboard is wanted."""
        from gantt_app.views.project_dashboard import ProjectDashboardFrame

        self.built += 1
        dashboard = ProjectDashboardFrame(self.panes, self.project)
        self.toolbar.set_dashboard(dashboard)
        return dashboard

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def showing(self):
        """The panes on the paned window, as Tk names them."""
        return list(self.panes.panes())

    def test_the_chart_is_what_the_window_opens_on(self):
        """The dashboard is somewhere to go, not the default."""
        self.assertIn(str(self.chart), self.showing())
        self.assertEqual(self.built, 0)

    def test_the_dashboard_takes_the_charts_place(self):
        """One pane goes and one arrives; the list keeps its own."""
        self.toolbar.show_dashboard()

        showing = self.showing()
        self.assertNotIn(str(self.chart), showing)
        self.assertIn(str(self.toolbar.dashboard_frame), showing)
        self.assertEqual(len(showing), 2, showing)

    def test_the_chart_comes_back(self):
        """And the dashboard goes, rather than the two stacking up."""
        self.toolbar.show_dashboard()
        self.toolbar.show_gantt_chart()

        showing = self.showing()
        self.assertIn(str(self.chart), showing)
        self.assertNotIn(str(self.toolbar.dashboard_frame), showing)
        self.assertEqual(len(showing), 2, showing)

    def test_choosing_the_same_view_twice_changes_nothing(self):
        """A reader who clicks Dashboard again still has two panes."""
        self.toolbar.show_dashboard()
        self.toolbar.show_dashboard()

        self.assertEqual(len(self.showing()), 2, self.showing())

    def test_the_dashboard_is_built_once_and_kept(self):
        """It is a panel most readers never open."""
        self.toolbar.show_dashboard()
        self.toolbar.show_gantt_chart()
        self.toolbar.show_dashboard()

        self.assertEqual(self.built, 1)

    def test_the_menu_offers_both_under_charts(self):
        """View > Charts, with the Gantt chart named first."""
        from gantt_app.views.toolbar import Toolbar

        view = [menu for menu in Toolbar._menu_definitions(self.toolbar)
                if menu['text'] == 'View'][0]
        charts = [item for item in view['items']
                  if item['text'] == 'Charts'][0]

        self.assertEqual([item['text'] for item in charts['submenu']],
                         ['Gantt Chart', 'Dashboard'])


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheDashboardFollowsThePlan(unittest.TestCase):
    """
    That an edit reaches the summary, through the real application.

    WHY THESE EXIST:
    ================
    A dashboard that was right when it was opened and stale afterwards is
    worse than no dashboard: every number on it still looks like a
    measurement. The chain it depends on - a change notifies
    on_project_changed, which is update_all, which refreshes all three
    panes - is four links long and entirely invisible, and nothing about
    the dashboard would look wrong if a link went.

    Built on the real GanttApp rather than a stand-in, because the wiring
    is what is being tested and a stand-in would be wired by the test.
    """

    def setUp(self):
        """The application, with the dashboard open on its sample plan."""
        from gantt_app.main import GanttApp

        self.app = GanttApp()
        self.app.withdraw()
        self.app.update_idletasks()

        self.app.toolbar.show_dashboard()
        self.dashboard = self.app.dashboard_frame
        self.dashboard.canvas.configure(width=1200, height=800)
        self.dashboard.refresh()

    def tearDown(self):
        """Tear it down."""
        try:
            self.app.destroy()
        except Exception:
            pass

    def texts(self):
        """Every piece of text the dashboard is showing."""
        canvas = self.dashboard.canvas
        return [canvas.itemcget(item, 'text') for item in canvas.find_all()
                if canvas.type(item) == 'text']

    def items_reported(self):
        """The count in the summary box, as a number."""
        for text in self.texts():
            if text.endswith(' Items'):
                return int(text.split()[0])
        raise AssertionError(f"no item count on the dashboard: {self.texts()}")

    def test_it_opens_on_the_plan_that_is_loaded(self):
        """Not on sample data, and not on nothing."""
        self.assertEqual(self.items_reported(),
                         len(self.app.project.tasks))

    def test_a_row_added_through_the_list_reaches_it(self):
        """The route every dialog and every import ends up taking."""
        before = self.items_reported()

        self.app.task_list.add_task(Task(
            id="900", name="Handover", task_type="Task",
            start_date=BASE, end_date=BASE, duration=4))

        self.assertEqual(self.items_reported(), before + 1)

    def test_a_row_removed_through_the_list_reaches_it(self):
        """And the other direction."""
        before = self.items_reported()
        going = self.app.project.tasks[-1].id

        self.app.task_list.remove_task(going)

        self.assertEqual(self.items_reported(), before - 1)

    def test_progress_typed_into_a_row_reaches_the_summary(self):
        """
        The number a reader is most likely to change, and most likely to
        go back to the dashboard to look at.
        """
        top = [task for task in self.app.project.tasks
               if task.parent_task_id is None and not task.effective_milestone]
        top[0].progress = 100
        self.app.update_all()

        self.assertNotIn("0.00%", self.texts())

    def test_it_is_refreshed_even_while_the_chart_is_the_one_on_show(self):
        """
        Or it would be right only until the first edit made behind its
        back, and a reader who switched away and back would be told the
        plan had not moved.
        """
        self.app.toolbar.show_gantt_chart()
        before = self.items_reported()

        self.app.task_list.add_task(Task(
            id="901", name="Retrospective", task_type="Task",
            start_date=BASE, end_date=BASE, duration=1))

        self.assertEqual(self.items_reported(), before + 1)


if __name__ == '__main__':
    unittest.main()

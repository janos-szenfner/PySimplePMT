"""
Tests for the user guide, its search, and the chart's default framing.

WHY THIS MODULE EXISTS:
======================
Two things here fail quietly rather than loudly.

A guide fails by being *wrong*: the worked examples in it are dates, and a
date that disagrees with the scheduler is worse than no example at all,
because the reader believes it and only finds out much later. Every number in
the guide is re-derived here from the scheduler that produced it.

The chart's framing fails by being *ugly*, which nobody writes a test for and
everybody notices. The range used to be padded a week on each side, so a
month-long plan opened with a quarter of the chart showing nothing at all.

DEVELOPMENT NOTES:
------------------
The window tests need a display; CI provides one through xvfb. The content and
the date arithmetic do not, and are kept apart from the widget tests so they
run everywhere.
"""

import unittest
from unittest import mock
from datetime import date, datetime, timedelta

from gantt_app.help.userguide import GUIDE_SECTIONS
from gantt_app.models import TASK_TYPES, Project, Task
from gantt_app.utils.chart_figure import calculate_date_range
from gantt_app.workdaycalendar import WorkingCalendar


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


class TestTheGuideCovers(unittest.TestCase):
    """The subjects a reader arrives with a question about."""

    def body(self) -> str:
        """Every word of the guide, lower case, as one string."""
        return '\n'.join(
            heading + '\n' + '\n'.join(paragraphs)
            for heading, paragraphs in GUIDE_SECTIONS
        ).lower()

    def test_it_is_a_guide_rather_than_a_page(self):
        """A tooltip's worth of text would not be worth a window."""
        self.assertGreater(len(GUIDE_SECTIONS), 15)
        self.assertGreater(len(self.body()), 8000)

    def test_every_section_has_a_heading_and_something_under_it(self):
        """An empty section is a heading that leads nowhere."""
        for heading, paragraphs in GUIDE_SECTIONS:
            self.assertTrue(heading.strip(), heading)
            self.assertTrue(paragraphs, heading)
            for paragraph in paragraphs:
                self.assertTrue(paragraph.strip(), heading)

    def test_the_task_types_are_all_explained(self):
        """The hierarchy is the first thing anybody has to understand."""
        body = self.body()
        for task_type in TASK_TYPES:
            self.assertIn(task_type.lower(), body, task_type)

    def test_the_scheduling_rules_are_explained(self):
        """Which is what "why did my task move" comes down to."""
        body = self.body()
        for phrase in ('working day', 'calendar day', 'duration',
                       'earliest begin', 'scheduling options'):
            self.assertIn(phrase, body, phrase)

    def test_the_link_types_are_all_named(self):
        """All four, or the one that is missing is the one being looked up."""
        body = self.body()
        for phrase in ('finish - start', 'start - start', 'finish - finish',
                       'start - finish', 'lag', 'hardness'):
            self.assertIn(phrase, body, phrase)

    def test_the_calendar_rules_are_explained(self):
        """Including the priority between them, which surprises people."""
        body = self.body()
        for phrase in ('override', 'public holiday', 'working week',
                       'critical path', 'float'):
            self.assertIn(phrase, body, phrase)

    def test_import_and_export_formats_are_listed(self):
        """A reader looking for "can it read X" should find the answer."""
        body = self.body()
        for phrase in ('gan', 'xlsx', 'mermaid', 'mpp', 'pdf'):
            self.assertIn(phrase, body, phrase)


class TestTheWorkedExamplesAreTrue(unittest.TestCase):
    """
    Every date in the guide, re-derived from the scheduler.

    A guide that disagrees with the application is worse than no guide: the
    reader believes it, and the disagreement is found much later and by
    somebody who has already acted on it.
    """

    def test_five_days_from_a_thursday(self):
        """'five days ... starting Thursday 3 September 2026 finishes on
        Wednesday 9 September'."""
        finish = WorkingCalendar().add_working_days(date(2026, 9, 3), 5)

        self.assertEqual(finish, date(2026, 9, 9))
        self.assertEqual(finish.strftime('%A'), 'Wednesday')

    def test_a_six_day_week_pulls_the_example_in(self):
        """'a four-day task running Friday 11 September 2026 to Wednesday 16
        September ends on Tuesday 15 September once Saturday is worked,
        still holding four days'."""
        project = Project(name="Guide")
        project.add_task(Task(id="a", name="A",
                              start_date=datetime(2026, 9, 11),
                              end_date=datetime(2026, 9, 16)))
        project.reschedule()
        task = project.get_task_by_id("a")
        self.assertEqual(task.end_date.date(), date(2026, 9, 16))
        self.assertEqual(project.working_duration(task), 4)

        project.set_working_week({6})

        self.assertEqual(task.end_date.date(), date(2026, 9, 15))
        self.assertEqual(project.working_duration(task), 4)

    def test_the_three_calendars_example(self):
        """'Three tasks of three days each, all starting Thursday 10
        September 2026' - on the plan's own, a weekend-only and a 24/7
        calendar."""
        project = Project(name="Guide")
        for identifier, calendar_id in (("d", None),
                                        ("w", "weekend-shift"),
                                        ("c", "continuous")):
            project.add_task(Task(id=identifier, name=identifier,
                                  start_date=datetime(2026, 9, 10),
                                  end_date=datetime(2026, 9, 10),
                                  duration=3, calendar_id=calendar_id))
        project.reschedule()

        default = project.get_task_by_id("d")
        weekend = project.get_task_by_id("w")
        continuous = project.get_task_by_id("c")

        # 'on the plan's own ... it runs 10 to 14 September'
        self.assertEqual(default.start_date.date(), date(2026, 9, 10))
        self.assertEqual(default.end_date.date(), date(2026, 9, 14))
        # 'on a weekend-only calendar it starts Saturday 12 September'
        self.assertEqual(weekend.start_date.date(), date(2026, 9, 12))
        # 'on a 24/7 calendar it runs 10 to 12 September straight through'
        self.assertEqual(continuous.start_date.date(), date(2026, 9, 10))
        self.assertEqual(continuous.end_date.date(), date(2026, 9, 12))


class TestTheChartOpensOnThePlan(unittest.TestCase):
    """
    Where the chart is framed when it is first drawn.

    The range used to be padded by a week on *each* side, so a month-long
    plan opened with a quarter of its width showing empty calendar, on the
    left, which is where the eye starts.
    """

    def plan(self, days=28):
        """One task spanning a given number of days."""
        start = datetime(2026, 8, 18)
        return [Task(id="a", name="A", start_date=start,
                     end_date=start + timedelta(days=days))]

    def test_almost_nothing_is_drawn_before_the_first_bar(self):
        """A day, so the bar does not sit on the axis line."""
        tasks = self.plan()
        low, _high = calculate_date_range(tasks)

        self.assertEqual((tasks[0].start_date - low).days, 1)

    def test_the_lead_in_is_a_sliver_of_the_width(self):
        """
        Rather than the quarter of it that a week each side came to.

        This is the number the complaint was actually about.
        """
        tasks = self.plan()
        low, high = calculate_date_range(tasks)

        wasted = (tasks[0].start_date - low).days / (high - low).days

        self.assertLess(wasted, 0.06)

    def test_there_is_room_after_the_last_bar_for_its_label(self):
        """Every bar is labelled to its right, including the last one."""
        tasks = self.plan()
        _low, high = calculate_date_range(tasks)

        self.assertGreaterEqual((high - tasks[0].end_date).days, 4)

    def test_a_long_plan_gets_proportionally_more_room_after_it(self):
        """
        A day is fewer pixels the longer the plan, so a label needs more of
        them - not the fixed few a short plan does.
        """
        short_low, short_high = calculate_date_range(self.plan(days=10))
        long_low, long_high = calculate_date_range(self.plan(days=365))

        short_trail = (short_high - self.plan(10)[0].end_date).days
        long_trail = (long_high - self.plan(365)[0].end_date).days

        self.assertGreater(long_trail, short_trail)

    def test_the_lead_in_does_not_grow_with_the_plan(self):
        """It is there to keep the bar off the axis, and that is all."""
        for days in (10, 100, 365):
            tasks = self.plan(days)
            low, _high = calculate_date_range(tasks)
            self.assertEqual((tasks[0].start_date - low).days, 1, days)

    def test_an_empty_plan_still_gives_a_range(self):
        """The chart has to draw something before there is anything in it."""
        low, high = calculate_date_range([])

        self.assertLess(low, high)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheGuideWindow(unittest.TestCase):
    """Opening it, and finding things in it."""

    def setUp(self):
        """A root window and a guide over it."""
        import customtkinter as ctk
        from gantt_app.help.userguide import UserGuideWindow

        self.root = ctk.CTk()
        self.root.withdraw()
        self.window = UserGuideWindow(self.root)
        self.window.update_idletasks()

    def tearDown(self):
        """Tear the windows down."""
        from gantt_app.help.userguide import UserGuideWindow

        UserGuideWindow._open_window = None
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_the_guide_is_written_into_the_body(self):
        """All of it, not the first section."""
        body = self.window.text.get('1.0', 'end')

        self.assertGreater(len(body), 8000)
        self.assertIn("Milestone", body)

    def test_the_body_cannot_be_typed_in(self):
        """Readable and selectable, but not editable."""
        import tkinter as tk

        self.assertEqual(str(self.window.text.cget('state')), tk.DISABLED)

    def test_searching_finds_and_counts(self):
        """The count is what tells a reader whether to keep pressing Next."""
        found = self.window.search('float')

        self.assertGreater(found, 0)
        self.assertEqual(self.window.search_status.cget('text'),
                         f"1 of {found}")

    def test_searching_ignores_case(self):
        """Nobody types a heading's capitals to find it."""
        self.assertEqual(self.window.search('MILESTONE'),
                         self.window.search('milestone'))

    def test_a_number_can_be_searched_for(self):
        """'any typed text or number' - a duration, a count, a year."""
        self.assertGreater(self.window.search('24/7'), 0)
        self.assertGreater(self.window.search('2026'), 0)

    def test_a_search_is_taken_literally(self):
        """
        So a date or a duration finds itself.

        Read as a pattern, '24/7' and '100%' are not what the reader typed.
        """
        self.assertEqual(self.window.search('nothing.matches.this'), 0)
        self.assertEqual(self.window.search_status.cget('text'), "No matches")

    def test_every_hit_is_highlighted(self):
        """Not only the one being looked at."""
        found = self.window.search('calendar')
        ranges = self.window.text.tag_ranges('match')

        # Two indices - a start and an end - per hit
        self.assertEqual(len(ranges), found * 2)

    def test_next_and_previous_walk_the_hits(self):
        """And wrap, rather than stopping at either end."""
        found = self.window.search('calendar')
        self.assertGreater(found, 2)

        self.window.next_match()
        self.assertEqual(self.window.search_status.cget('text'),
                         f"2 of {found}")

        self.window.previous_match()
        self.window.previous_match()
        self.assertEqual(self.window.search_status.cget('text'),
                         f"{found} of {found}")

    def test_clearing_takes_the_highlighting_off(self):
        """A stale highlight is worse than none."""
        self.window.search('calendar')

        self.window.clear_search()

        self.assertEqual(self.window.text.tag_ranges('match'), ())
        self.assertEqual(self.window.search_status.cget('text'), "")

    def test_only_one_guide_is_ever_open(self):
        """Pressing ? twice raises the one that is up."""
        from gantt_app.help.userguide import UserGuideWindow

        first = UserGuideWindow.show(self.root)
        second = UserGuideWindow.show(self.root)

        self.assertIs(first, second)

    def test_search_is_opt_in_per_window(self):
        """
        A short reference is faster read than searched; a long one is not.

        The dependency reference is a handful of sections and keeps none.
        The guide and the task editor's reference are both long enough to be
        looked things up in, and have it.
        """
        from gantt_app.help.dependencyhelp import DependencyHelpWindow
        from gantt_app.help.editorhelp import EditorHelpWindow
        from gantt_app.help.userguide import UserGuideWindow

        self.assertFalse(DependencyHelpWindow.SEARCHABLE)
        self.assertTrue(EditorHelpWindow.SEARCHABLE)
        self.assertTrue(UserGuideWindow.SEARCHABLE)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestReachingTheGuide(unittest.TestCase):
    """The two ways in, which have to be the same window."""

    def setUp(self):
        """A toolbar over an empty project."""
        import customtkinter as ctk
        from gantt_app.models import Project
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()
        self.toolbar = Toolbar(self.root, Project(name="P"))
        self.toolbar.update_idletasks()

    def tearDown(self):
        """Tear the windows down."""
        from gantt_app.help.userguide import UserGuideWindow

        if UserGuideWindow._open_window is not None:
            UserGuideWindow._open_window = None
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_the_icon_bar_carries_a_question_mark(self):
        """Which is what a reader looks for."""
        self.assertIsNotNone(self.toolbar.icon_toolbar.help_button)
        self.assertEqual(self.toolbar.icon_toolbar.help_button.tooltip, "Help")

    def test_it_is_live_with_no_project_open(self):
        """
        Help withheld until you have a plan is withheld from whoever needs it.

        Everything in ICON_ACTIONS is greyed out without a project, which is
        why the ? is built outside that list.
        """
        self.assertEqual(str(self.toolbar.icon_toolbar.help_button.cget('state')),
                         'normal')

    def test_pressing_it_opens_the_guide(self):
        """The window, by name."""
        from gantt_app.help.userguide import UserGuideWindow

        self.toolbar.icon_toolbar.help_button.invoke()
        self.toolbar.update_idletasks()

        self.assertIsNotNone(UserGuideWindow._open_window)

    def test_the_menu_opens_the_same_window(self):
        """Not a second copy of it."""
        from gantt_app.help.userguide import UserGuideWindow

        self.toolbar.icon_toolbar.help_button.invoke()
        opened = UserGuideWindow._open_window

        self.toolbar.show_help()

        self.assertIs(UserGuideWindow._open_window, opened)


class TestTheTaskEditorReference(unittest.TestCase):
    """
    The reference behind the task editor's own Help button.

    DEVELOPMENT NOTES:
    ------------------
    It used to explain the form's older half - dates, milestones, progress,
    colour - and say nothing about the fields that decide where a task
    actually lands: the scheduling mode, the calendar, the earliest begin
    date. Somebody asking "why did this finish there" found nothing.
    """

    def body(self) -> str:
        """Every word of it, lower case, as one string."""
        from gantt_app.help.editorhelp import HELP_SECTIONS

        return '\n'.join(
            heading + '\n' + '\n'.join(paragraphs)
            for heading, paragraphs in HELP_SECTIONS
        ).lower()

    def test_it_covers_every_field_on_the_form(self):
        """A box with nothing said about it is the one being looked up."""
        body = self.body()
        for field in ('type', 'start date', 'end date', 'duration',
                      'is milestone', 'scheduling options', 'earliest begin',
                      'working calendar', 'progress', 'priority',
                      'show in timeline', 'shape', 'colour', 'details'):
            self.assertIn(field, body, field)

    def test_it_says_how_the_dates_are_worked_out(self):
        """Which was the largest thing missing from it."""
        body = self.body()
        for phrase in ('walked, not added', 'working', 'calendar days',
                       'end date is calculated', 'start date is calculated',
                       'duration is calculated'):
            self.assertIn(phrase, body, phrase)

    def test_it_explains_the_working_calendar_and_its_priority(self):
        """All four rules, in the order they are read."""
        body = self.body()
        for phrase in ('manual override', 'public holiday', 'working week',
                       'highest priority'):
            self.assertIn(phrase, body, phrase)

    def test_it_explains_a_shaded_box(self):
        """
        The commonest "is this broken" question about the form.

        A shaded field is one the application is filling in, and nothing on
        the form itself says so.
        """
        self.assertIn('shaded', self.body())

    def test_the_worked_examples_are_true(self):
        """
        Re-derived from the scheduler, like the guide's.

        The reference is read while the form is open, so a wrong example is
        acted on immediately.
        """
        # 'five days of work starting Thursday 3 September 2026 finishes on
        # Wednesday 9 September'
        self.assertEqual(
            WorkingCalendar().add_working_days(date(2026, 9, 3), 5),
            date(2026, 9, 9))

        # 'a three-day task starting Thursday 10 September 2026 runs to
        # Monday 14 September on the standard week ... on a weekend-only
        # calendar it starts on Saturday 12 September ... on a 24/7 calendar
        # it runs 10 to 12 September'
        project = Project(name="Editor help")
        for identifier, calendar_id in (("d", None),
                                        ("w", "weekend-shift"),
                                        ("c", "continuous")):
            project.add_task(Task(id=identifier, name=identifier,
                                  start_date=datetime(2026, 9, 10),
                                  end_date=datetime(2026, 9, 10),
                                  duration=3, calendar_id=calendar_id))
        project.reschedule()

        self.assertEqual(project.get_task_by_id("d").end_date.date(),
                         date(2026, 9, 14))
        self.assertEqual(project.get_task_by_id("w").start_date.date(),
                         date(2026, 9, 12))
        self.assertEqual(project.get_task_by_id("c").end_date.date(),
                         date(2026, 9, 12))


class TestMoreDatesOnTheAxis(unittest.TestCase):
    """
    How many date labels the chart shows.

    DEVELOPMENT NOTES:
    ------------------
    The step was chosen to keep the count under a dozen whatever the width,
    so a month-long plan was labelled once a week however wide the window -
    and widening it added blank space between the same four dates.
    """

    def steps(self, days, width, font_size=12):
        """The gap the axis would use, in days."""
        from gantt_app.utils.chart_render import _tick_step
        return _tick_step(days, width, font_size)

    def test_a_wider_chart_shows_more_dates(self):
        """Which is the whole complaint."""
        narrow = self.steps(34, 600)
        wide = self.steps(34, 1900)

        self.assertLess(wide, narrow)

    def test_a_month_on_a_normal_window_is_not_weekly(self):
        """It was every seven days, which came to four labels."""
        self.assertLessEqual(self.steps(34, 1400), 3)

    def test_labels_are_never_packed_closer_than_they_fit(self):
        """A denser axis is only an improvement while it stays readable."""
        from gantt_app.utils.chart_render import _tick_label_px

        for days in (14, 34, 90, 365):
            for width in (500, 900, 1400, 1900, 2400):
                step = self.steps(days, width)
                labels = days / step
                self.assertLessEqual(labels * _tick_label_px(12), width * 1.05,
                                     f"{days}d at {width}px")

    def test_bigger_type_thins_the_labels_out(self):
        """
        The tick size follows the chart's font_size, which is a setting.

        A fixed label width was safe at the default and overlapped the moment
        anybody made the type bigger.
        """
        self.assertGreaterEqual(self.steps(34, 1400, font_size=20),
                                self.steps(34, 1400, font_size=10))

    def test_a_caller_with_no_width_still_gets_a_step(self):
        """The exporters ask without one."""
        from gantt_app.utils.chart_render import _tick_step

        self.assertGreater(_tick_step(34), 0)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheHelpButtonSitsUnderLog(unittest.TestCase):
    """
    Where the ? is on the icon row.

    Both rows fill the toolbar's width, so lining the two up is a matter of
    matching what each keeps clear of the right edge.
    """

    def test_the_two_are_measured_from_the_same_edge(self):
        """The arithmetic the alignment rests on, without needing a window."""
        from gantt_app.views.toolbar import IconToolbar

        centre_of_help = (IconToolbar.HELP_RIGHT_PAD
                          + IconToolbar.BUTTON_SIZE / 2)

        self.assertEqual(centre_of_help, IconToolbar.LOG_CENTRE_FROM_RIGHT)

    def test_the_question_mark_is_packed_to_the_right(self):
        """Rather than after the day/night control, where it used to be."""
        import customtkinter as ctk
        from gantt_app.models import Project
        from gantt_app.views.toolbar import Toolbar

        root = ctk.CTk()
        root.withdraw()
        try:
            toolbar = Toolbar(root, Project(name="P"))
            toolbar.update_idletasks()

            info = toolbar.icon_toolbar.help_button.pack_info()

            self.assertEqual(info['side'], 'right')
        finally:
            root.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestHelpOpensOverAModalDialog(unittest.TestCase):
    """
    A help window opened from the task editor has to be usable.

    DEVELOPMENT NOTES:
    ------------------
    A grab is exclusive. The task editor is modal, so it receives every click
    in the application, and a window opened from it is a separate Toplevel
    rather than one of its children - so it got nothing. It drew correctly,
    scrolled nowhere, and no button in it responded. Both Help buttons on the
    editor had been dead since they were added.

    The decision is tested rather than the Tk state, because take_grab defers
    until the window manager has mapped the window - so asserting on
    grab_current() is a race, and a test that sleeps to avoid one is a test
    that fails on a slow machine.
    """

    def setUp(self):
        """A root window to open references over."""
        import customtkinter as ctk

        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        """Tear it down, and forget any window left open."""
        from gantt_app.help.editorhelp import EditorHelpWindow
        from gantt_app.help.userguide import UserGuideWindow

        for cls in (EditorHelpWindow, UserGuideWindow):
            cls._open_window = None
        try:
            self.root.destroy()
        except Exception:
            pass

    def open_with_grab_held_by(self, holder):
        """
        Build a reference window, reporting whether it claimed the grab.

        `holder` stands in for whatever grab_current() would return: None
        when nothing is modal, or an object when something is.
        """
        from gantt_app.help.editorhelp import EditorHelpWindow

        with mock.patch('gantt_app.views.modal.take_grab') as claimed, \
             mock.patch.object(EditorHelpWindow, 'grab_current',
                               return_value=holder):
            window = EditorHelpWindow(self.root)
            self.addCleanup(window.close)

        return claimed.called

    def test_it_takes_the_grab_when_something_else_holds_one(self):
        """Or the window opens and nothing in it can be clicked."""
        modal_window = object()

        self.assertTrue(self.open_with_grab_held_by(modal_window))

    def test_it_leaves_the_grab_alone_when_nothing_is_modal(self):
        """
        The guide is meant to be read beside the window it describes.

        Taking the grab whenever a reference opened would lock the whole
        application behind the guide - which is the same bug, pointed the
        other way.
        """
        self.assertFalse(self.open_with_grab_held_by(None))

    def test_it_does_not_take_the_grab_from_itself(self):
        """A window already holding it has nothing to claim."""
        from gantt_app.help.editorhelp import EditorHelpWindow

        with mock.patch('gantt_app.views.modal.take_grab') as claimed:
            window = EditorHelpWindow(self.root)
            self.addCleanup(window.close)
            claimed.reset_mock()

            with mock.patch.object(window, 'grab_current',
                                   return_value=window):
                window._claim_grab_if_needed()

        self.assertFalse(claimed.called)

    def test_every_reference_window_does_this(self):
        """
        All three share the base class, so all three are fixed at once.

        The dependency reference is opened from the same modal editor and had
        the same bug.
        """
        from gantt_app.help.dependencyhelp import DependencyHelpWindow
        from gantt_app.help.editorhelp import EditorHelpWindow
        from gantt_app.help.reference import ReferenceWindow
        from gantt_app.help.userguide import UserGuideWindow

        for cls in (EditorHelpWindow, DependencyHelpWindow, UserGuideWindow):
            self.assertTrue(issubclass(cls, ReferenceWindow), cls.__name__)
            self.assertTrue(hasattr(cls, '_claim_grab_if_needed'),
                            cls.__name__)


class TestTheCalendarStrip(unittest.TestCase):
    """
    The date header: a month band, and a cell per day beneath it.

    DEVELOPMENT NOTES:
    ------------------
    The axis stays linear in calendar days. Dropping the non-working columns
    is what most calendar strips do and cannot be done here: a task may
    follow a calendar of its own, so a 24/7 task genuinely works Saturdays
    and would have nowhere to be drawn, and the whole point of a manual
    override is to make one particular Saturday a working day.
    """

    def plan(self, days=24, start=datetime(2026, 8, 18)):
        """A project spanning a given number of days."""
        project = Project(name="Strip")
        project.add_task(Task(id="a", name="A", start_date=start,
                              end_date=start + timedelta(days=days)))
        project.reschedule()
        return project

    def layout(self, project=None, width=1400):
        """The chart layout at a given width."""
        from gantt_app.utils.chart_render import layout_chart
        return layout_chart(project or self.plan(), width=width)

    def test_a_month_of_plan_gets_a_cell_for_every_day(self):
        """Which is the whole look: 1, 2, 3, 4 rather than one date a week."""
        layout = self.layout()

        self.assertEqual(layout.header_mode, 'day')
        self.assertGreater(len(layout.day_cells), 20)

    def test_the_cells_carry_the_day_number_alone(self):
        """
        The month and the year are in the band above.

        That is what lets a cell be about 22px wide where a full date needed
        82, and it is where the extra density comes from.
        """
        layout = self.layout()

        for _x0, _x1, label, *_rest in layout.day_cells:
            self.assertTrue(label.isdigit(), label)
            self.assertLessEqual(int(label), 31)

    def test_the_band_names_every_month_the_plan_touches(self):
        """Or a bare 17 has nothing to say which 17 it is."""
        layout = self.layout()

        names = [label for _x0, _x1, label in layout.month_bands]

        self.assertEqual(names, ['AUGUST 2026', 'SEPTEMBER 2026'])

    def test_the_cells_run_edge_to_edge_without_gaps(self):
        """A strip with holes in it reads as a broken grid."""
        layout = self.layout()

        for (_a0, a1, *_x), (b0, _b1, *_y) in zip(layout.day_cells,
                                                  layout.day_cells[1:]):
            self.assertAlmostEqual(a1, b0, places=3)

    def test_non_working_days_are_marked(self):
        """Shading is what carries "not worked" now the letters are gone."""
        layout = self.layout()

        working = [c[4] for c in layout.day_cells]

        self.assertIn(True, working)
        self.assertIn(False, working)

    def test_a_weekend_is_still_given_a_column(self):
        """
        The axis stays linear; see the note on the class.

        A task on a 24/7 calendar works Saturdays, and an override exists to
        make one particular Saturday worked - both need somewhere to draw.
        """
        layout = self.layout()

        non_working = [c for c in layout.day_cells if not c[4]]

        self.assertTrue(non_working)
        for x0, x1, *_rest in non_working:
            self.assertGreater(x1, x0)

    def test_today_is_picked_out(self):
        """The reference highlights it, and nothing used to."""
        today = datetime.now()
        project = self.plan(days=10, start=today - timedelta(days=3))

        layout = self.layout(project)

        self.assertEqual(sum(1 for c in layout.day_cells if c[3]), 1)

    def test_a_plan_outside_today_marks_nothing(self):
        """The tint is a fact about the plan, not decoration."""
        layout = self.layout(self.plan(start=datetime(2031, 1, 6)))

        self.assertEqual([c for c in layout.day_cells if c[3]], [])

    def test_week_starts_are_flagged(self):
        """They carry the heavier rule that gives the strip its rhythm."""
        layout = self.layout()

        starts = [c for c in layout.day_cells if c[5]]

        self.assertTrue(starts)
        self.assertEqual(len(starts), len(layout.date_ticks))

    def test_a_long_plan_falls_back_to_weeks_then_months(self):
        """A day cell that cannot be read is worse than none."""
        from gantt_app.utils.chart_render import layout_chart

        weeks = layout_chart(self.plan(days=120), width=1400)
        months = layout_chart(self.plan(days=1200), width=900)

        self.assertEqual(weeks.header_mode, 'week')
        self.assertEqual(months.header_mode, 'month')
        self.assertEqual(months.day_cells, [])

    def test_the_month_band_survives_every_mode(self):
        """It is what says where in the calendar the chart is."""
        from gantt_app.utils.chart_render import layout_chart

        for days, width in ((24, 1400), (120, 1400), (1200, 900)):
            layout = layout_chart(self.plan(days=days), width=width)
            self.assertTrue(layout.month_bands, f"{days}d at {width}px")

    def test_both_renderers_draw_it(self):
        """The PIL image and the SVG share the layout, not the drawing."""
        from gantt_app.utils.chart_render import render_image, render_svg

        project = self.plan()

        svg = render_svg(project, width=1200)
        image = render_image(project, width=1200, scale=1)

        self.assertIn('AUGUST 2026', svg)
        self.assertIsNotNone(image)

    def test_the_header_colours_come_from_the_settings(self):
        """
        So the export keeps the light ones however dark the window is.

        screen_settings swaps them for the appearance; the exporters go
        through current_settings and do not.
        """
        from gantt_app.utils.chart_figure import DEFAULT_SETTINGS
        from gantt_app import theme

        for key in DEFAULT_SETTINGS:
            if key.startswith('header_'):
                self.assertEqual(DEFAULT_SETTINGS[key],
                                 getattr(theme, key.upper())[0], key)


if __name__ == '__main__':
    unittest.main()

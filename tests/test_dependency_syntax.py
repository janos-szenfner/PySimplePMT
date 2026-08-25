"""
Tests for the Dependencies column: the grammar, and typing into the grid.

WHY THIS MODULE EXISTS:
======================
"003SS+1d" is how every planning tool has spelt a dependency for thirty years,
and the column now takes it. That makes the grammar a contract - what a reader
types, and what is written back into the cell afterwards, have to be the same
language or the column loses work every time it normalises.

So the first half of this walks the specification's token table, and the
second half checks the round trip: what the cell shows can be typed straight
back in and mean the same thing.

The rest is what a number alone cannot answer. A cell can name a task that is
not there, name itself, name the same task twice, or close a loop - and a
column that quietly dropped any of those would leave the reader comparing what
they typed against what came back to notice.

DEVELOPMENT NOTES:
------------------
The grammar tests need no display. The grid half does, and skips without one.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.dependencysyntax import format_links, parse
from gantt_app.models import Dependency, Project, Task

BASE = datetime(2026, 8, 25)


class TheGrammarTestCase(unittest.TestCase):
    """One link, read out of a cell."""

    def one(self, text: str):
        """The single link a cell holds, insisting there is exactly one."""
        links, errors = parse(text)
        self.assertEqual(errors, [], text)
        self.assertEqual(len(links), 1, text)
        return links[0]


class TestTheSpecificationsTable(TheGrammarTestCase):
    """Every row of the token reference, in order."""

    def test_a_bare_number_is_finish_to_start(self):
        """The default, and by a long way the commonest link."""
        link = self.one('003')

        self.assertEqual((link.number, link.dep_type, link.lag), ('003', 'FS', 0))

    def test_a_type_and_a_lag_in_days(self):
        """003FS+2d."""
        link = self.one('003FS+2d')

        self.assertEqual((link.dep_type, link.lag, link.lag_unit),
                         ('FS', 2, 'days'))

    def test_a_negative_lag_is_lead_time(self):
        """003SS-1d, which is how a schedule is compressed."""
        link = self.one('003SS-1d')

        self.assertEqual((link.dep_type, link.lag), ('SS', -1))

    def test_a_type_with_no_lag(self):
        """003FF."""
        link = self.one('003FF')

        self.assertEqual((link.dep_type, link.lag), ('FF', 0))

    def test_a_lag_as_a_share_of_the_predecessor(self):
        """003SF+50%, which says 'when that one is half done'."""
        link = self.one('003SF+50%')

        self.assertEqual((link.dep_type, link.lag, link.lag_unit),
                         ('SF', 50, 'percent'))


class TestWhatElseTheCellTakes(TheGrammarTestCase):
    """The forms a reader will type without being told to."""

    def test_several_links_separated_by_commas(self):
        """The example from the specification."""
        links, errors = parse('001, 003SS+1d')

        self.assertEqual(errors, [])
        self.assertEqual([(link.number, link.dep_type, link.lag)
                          for link in links],
                         [('001', 'FS', 0), ('003', 'SS', 1)])

    def test_semicolons_separate_them_too(self):
        """A plan pasted out of a spreadsheet uses whichever its locale does."""
        links, _errors = parse('001;003')

        self.assertEqual(len(links), 2)

    def test_the_case_of_the_type_does_not_matter(self):
        """Nobody holds shift for this."""
        self.assertEqual(self.one('3ss').dep_type, 'SS')

    def test_spaces_anywhere_sensible(self):
        """A cell that has been read back and edited collects them."""
        link = self.one(' 3 fs + 2 days ')

        self.assertEqual((link.dep_type, link.lag, link.lag_unit),
                         ('FS', 2, 'days'))

    def test_a_lag_with_no_type(self):
        """003+2d means Finish-Start with two days on it."""
        link = self.one('003+2d')

        self.assertEqual((link.dep_type, link.lag), ('FS', 2))

    def test_a_lag_with_no_unit_is_days(self):
        """Which is what it is everywhere else in the application."""
        self.assertEqual(self.one('003FS+2').lag_unit, 'days')

    def test_an_empty_cell_is_no_links_rather_than_an_error(self):
        """It is how a cell is cleared."""
        self.assertEqual(parse(''), ([], []))
        self.assertEqual(parse('   ,  ; '), ([], []))


class TestWhatItRefuses(unittest.TestCase):
    """Nothing is guessed at, and nothing vanishes without a word."""

    def test_a_token_it_cannot_read_is_reported(self):
        """
        Rather than dropped.

        A column where one bad token silently disappears is a column that
        loses work: three links go in, two come back, no reason given.
        """
        links, errors = parse('abc')

        self.assertEqual(links, [])
        self.assertEqual(len(errors), 1)
        self.assertIn('abc', errors[0])

    def test_the_message_says_what_the_grammar_is(self):
        """An error naming only the problem leaves the reader guessing."""
        _links, errors = parse('003XX')

        self.assertIn('003SS+1d', errors[0])

    def test_a_lag_with_no_number_is_refused(self):
        """'003FS+' is half a thought, not a link with no lag."""
        self.assertEqual(parse('003FS+')[0], [])

    def test_the_good_tokens_in_a_bad_cell_are_still_read(self):
        """So the caller can say which part failed."""
        links, errors = parse('001, junk, 003')

        self.assertEqual(len(links), 2)
        self.assertEqual(len(errors), 1)


class TestTheRoundTrip(unittest.TestCase):
    """What the cell shows is what the cell takes."""

    def test_every_form_survives_being_written_and_read(self):
        """
        The contract the column rests on.

        A cell is normalised after every edit, so a form that came out
        differently from how it went in would rewrite the reader's work.
        """
        for dep_type, lag, unit in (('FS', 0, 'days'), ('FS', 2, 'days'),
                                    ('SS', -1, 'days'), ('FF', 0, 'days'),
                                    ('SF', 50, 'percent')):
            link = Dependency('the-key', dep_type, 'Hard', lag, unit)
            written = link.to_syntax_string(3)

            read = parse(written)[0]

            self.assertEqual(len(read), 1, written)
            self.assertEqual(read[0].number, '3', written)
            self.assertEqual(read[0].dep_type, dep_type, written)
            self.assertEqual(read[0].lag, lag, written)
            self.assertEqual(read[0].lag_unit, unit, written)

    def test_a_plain_link_is_written_as_the_number_alone(self):
        """'003FS' on every ordinary link would be noise."""
        self.assertEqual(Dependency('k').to_syntax_string('003'), '003')

    def test_the_type_comes_back_when_there_is_a_lag(self):
        """'003+2d' reads as if the type had been left out by mistake."""
        self.assertEqual(Dependency('k', 'FS', 'Hard', 2).to_syntax_string(3),
                         '3FS+2d')

    def test_links_are_written_comma_separated(self):
        """Which is what parse splits on."""
        numbers = {'a': 1, 'b': 3}
        links = [Dependency('a'), Dependency('b', 'SS', 'Hard', 1)]

        self.assertEqual(format_links(links, numbers), '1, 3SS+1d')

    def test_a_link_to_a_task_that_has_gone_is_not_written(self):
        """Inventing a number for it would produce a cell parse refuses."""
        self.assertEqual(format_links([Dependency('gone')], {'a': 1}), '')

    def test_the_unit_survives_a_saved_file(self):
        """A share of a duration is not the same as that many days."""
        link = Dependency('k', 'SF', 'Hard', 50, 'percent')

        self.assertEqual(Dependency.from_any(link.to_dict()).lag_unit,
                         'percent')

    def test_a_link_saved_before_units_existed_reads_as_days(self):
        """Which is what every one of them meant."""
        self.assertEqual(
            Dependency.from_any({'task_id': 'k', 'lag': 2}).lag_unit, 'days')


class TestTheCellIsCheckedAgainstThePlan(unittest.TestCase):
    """What a number alone cannot answer."""

    def setUp(self):
        """Three tasks, numbered 1 to 3."""
        self.project = Project(name="Plan")
        for task_id in ('first', 'second', 'third'):
            self.project.add_task(Task(id=task_id, name=task_id,
                                       task_type="Task", start_date=BASE,
                                       end_date=BASE + timedelta(days=2)))

    def read(self, text, task='third'):
        """Parse a cell against the plan."""
        return self.project.parse_dependencies(task, text)

    def test_a_number_becomes_the_task_it_names(self):
        """
        The cell holds the number; the link holds the identity.

        The number moves when rows move and the identity does not, which is
        what keeps a link pointing at the task it was given.
        """
        links, errors = self.read('1')

        self.assertEqual(errors, [])
        self.assertEqual(links[0].task_id, 'first')

    def test_a_number_naming_nothing_is_refused(self):
        """Typing 9 in a plan of three is a typo, not a link."""
        links, errors = self.read('9')

        self.assertEqual(links, [])
        self.assertIn('no task 9', errors[0])

    def test_a_task_cannot_depend_on_itself(self):
        """The specification's self-reference guard."""
        links, errors = self.read('3')

        self.assertEqual(links, [])
        self.assertIn('itself', errors[0])

    def test_the_same_task_twice_is_refused(self):
        """One of them would silently replace the other."""
        links, errors = self.read('1, 1')

        self.assertEqual(len(links), 1)
        self.assertIn('more than once', errors[0])

    def test_a_loop_is_refused(self):
        """
        The specification's circular reference guard.

        A plan with a loop cannot be scheduled - every pass moves a task and
        the next pass moves it back - so it is caught before it is stored.
        """
        self.project.get_task_by_id('second').add_dependency('third')

        links, errors = self.read('2')

        self.assertEqual(links, [])
        self.assertIn('circle', errors[0])

    def test_a_loop_formed_within_one_cell_is_refused(self):
        """
        Typing '1, 2' where 2 already waits for 1 is a loop that only exists
        once both have been taken - so each is checked against the ones
        already accepted, not only against what the task holds now.
        """
        self.project.get_task_by_id('second').add_dependency('third')

        links, errors = self.read('1, 2')

        self.assertEqual([link.task_id for link in links], ['first'])
        self.assertTrue(errors)

    def test_a_task_cannot_depend_on_its_own_subtask(self):
        """
        Which is a loop through the hierarchy rather than through links.

        The number is looked up rather than written here: moving a task
        under another changes the display order, so which task '1' names
        changes with it. That is the numbering working, not a hazard - but
        a test that hard-coded the number would be asserting about a
        different task than it meant to.
        """
        self.project.get_task_by_id('first').parent_task_id = 'third'
        child = self.project.display_ids()['first']

        links, errors = self.read(str(child))

        self.assertEqual(links, [])
        self.assertTrue(errors)

    def test_the_plan_is_left_alone_by_a_check_that_fails(self):
        """
        The cycle check puts the candidate links on the task to ask about
        them. A plan left holding a probe's links would be a far worse fault
        than the one being guarded against.
        """
        before = list(self.project.get_task_by_id('third').dependencies)

        self.read('1, 2, 9')

        self.assertEqual(list(self.project.get_task_by_id('third').dependencies),
                         before)


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


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TestTypingIntoTheGrid(unittest.TestCase):
    """The column itself: what it shows, and what it stores."""

    def setUp(self):
        """A list over three tasks, with an undo history behind it."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        for task_id, name in (('u1', 'Planning'), ('u2', 'Design'),
                              ('u3', 'Build')):
            self.project.add_task(Task(id=task_id, name=name,
                                       task_type="Task", start_date=BASE,
                                       end_date=BASE + timedelta(days=2)))

        self.manager = UndoRedoManager()
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project, self.manager))
        self.root.update_idletasks()

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def cell(self, task_id: str) -> str:
        """What the Dependencies column shows for a row."""
        return self.task_list.tree.set(task_id, 'Dependencies')

    def test_an_empty_cell_says_so(self):
        """Rather than showing nothing at all."""
        self.assertEqual(self.cell('u3'), 'None')

    def test_what_is_stored_is_shown_in_the_grammar(self):
        """So the cell can be typed straight back in."""
        links, _errors = self.project.parse_dependencies('u3', '1, 2SS+1d')

        self.task_list.set_dependencies('u3', links)

        self.assertEqual(self.cell('u3'), '1, 2SS+1d')

    def test_the_cell_normalises_to_the_same_text(self):
        """
        The round trip, through the grid this time.

        A cell that came back differently from how it went in would rewrite
        the reader's work every time they pressed Enter.
        """
        for typed in ('1', '1FS+2d', '2SS-1d', '2FF', '1SF+50%'):
            links, errors = self.project.parse_dependencies('u3', typed)
            self.assertEqual(errors, [], typed)

            self.task_list.set_dependencies('u3', links)

            self.assertEqual(self.cell('u3'), typed)

    def test_a_whole_cell_is_one_undo_step(self):
        """Typing a column of links should not cost a press each to undo."""
        links, _errors = self.project.parse_dependencies('u3', '1, 2')
        depth = len(self.manager.undo_stack)

        self.task_list.set_dependencies('u3', links)

        self.assertEqual(len(self.manager.undo_stack), depth + 1)

    def test_undo_puts_the_cell_back(self):
        """Both the links and what the column shows."""
        links, _errors = self.project.parse_dependencies('u3', '1, 2')
        self.task_list.set_dependencies('u3', links)

        self.manager.undo()
        self.task_list.update_task_list()

        self.assertEqual(self.cell('u3'), 'None')

    def test_the_task_editor_shows_what_the_grid_stored(self):
        """
        Which is the point of storing real links rather than a string.

        A cell that only changed what the column displayed would leave the
        editor showing nothing, and the next save would write that nothing
        back over it.
        """
        links, _errors = self.project.parse_dependencies('u3', '1, 2SS+1d')
        self.task_list.set_dependencies('u3', links)

        stored = self.project.get_task_by_id('u3').dependencies

        self.assertEqual([(link.task_id, link.dep_type, link.lag)
                          for link in stored],
                         [('u1', 'FS', 0), ('u2', 'SS', 1)])

    def test_a_cell_with_an_error_stores_nothing(self):
        """
        Not even the half of it that parsed.

        Storing the good half would silently drop the rest, and the reader
        would have to compare what they typed against what came back.
        """
        from unittest import mock

        self.task_list._cell_editor = mock.Mock(get=lambda: '1, 9')
        self.task_list._cell_editor_task = 'u3'

        with mock.patch('gantt_app.views.task_list.messagebox.showerror') as told:
            self.task_list._commit_dependencies()

        self.assertTrue(told.called, "the reader was not told")
        self.assertEqual(list(self.project.get_task_by_id('u3').dependencies), [])

    def test_a_cell_that_reads_stores_it(self):
        """The same path, with something it can read."""
        from unittest import mock

        self.task_list._cell_editor = mock.Mock(get=lambda: '1')
        self.task_list._cell_editor_task = 'u3'

        self.task_list._commit_dependencies()

        self.assertEqual([link.task_id for link in
                          self.project.get_task_by_id('u3').dependencies],
                         ['u1'])

    def test_clearing_the_cell_removes_the_links(self):
        """An empty cell means no links, not 'leave them alone'."""
        from unittest import mock

        links, _errors = self.project.parse_dependencies('u3', '1')
        self.task_list.set_dependencies('u3', links)

        self.task_list._cell_editor = mock.Mock(get=lambda: '')
        self.task_list._cell_editor_task = 'u3'
        self.task_list._commit_dependencies()

        self.assertEqual(list(self.project.get_task_by_id('u3').dependencies), [])

    def test_the_dependencies_column_is_the_one_that_edits(self):
        """
        Double-clicking anywhere else still folds the branch.

        The column is found by name rather than by number: adding a column
        shifts every one after it, and a check against '#8' would go on
        working and mean something else.
        """
        columns = self.task_list.tree.cget('columns')

        self.assertIn('Dependencies', columns)



class TestTheEngineIsUnchanged(unittest.TestCase):
    """
    A lag in days schedules exactly what it scheduled before.

    WHY THIS EXISTS:
    ================
    Adding a unit to the lag put a branch in front of every read of it. The
    whole of the existing plan is in days, so that branch has to be
    invisible: the scheduler must compute the same dates it always did, and
    a percentage - which could not previously be stated at all - is the only
    thing that behaves differently.
    """

    def plan(self, lag=0, lag_unit='days', dep_type='FS'):
        """Two five-day tasks, the second waiting on the first."""
        project = Project(name="Plan")
        # Monday 17 August 2026, so every weekday below is known
        monday = datetime(2026, 8, 17)
        project.add_task(Task(id='first', name='First', task_type='Task',
                              start_date=monday,
                              end_date=monday + timedelta(days=4)))
        project.add_task(Task(id='second', name='Second', task_type='Task',
                              start_date=monday,
                              end_date=monday + timedelta(days=4)))
        project.get_task_by_id('second').add_dependency(
            'first', dep_type, 'Hard', lag, lag_unit)
        project.reschedule()
        return project

    def test_a_plain_link_starts_the_next_working_day(self):
        """Friday finish, Monday start - the weekend is not worked."""
        project = self.plan()

        self.assertEqual(project.get_task_by_id('second').start_date.date(),
                         datetime(2026, 8, 24).date())

    def test_a_lag_in_days_is_read_as_days(self):
        """Two working days after, so the Wednesday."""
        project = self.plan(lag=2)

        self.assertEqual(project.get_task_by_id('second').start_date.date(),
                         datetime(2026, 8, 26).date())

    def test_a_lead_in_days_pulls_it_back(self):
        """Negative lag overlaps the two, which is how a plan is compressed."""
        early = self.plan(lag=-2).get_task_by_id('second').start_date
        plain = self.plan().get_task_by_id('second').start_date

        self.assertLess(early, plain)

    def test_the_days_path_does_not_go_near_the_new_arithmetic(self):
        """
        A lag in days is returned untouched, by construction.

        This is the assertion that says the branch is invisible: whatever
        lag_days does for a percentage, for days it hands back the number
        the link holds.
        """
        project = self.plan(lag=3)
        link = project.get_task_by_id('second').dependencies[0]

        self.assertEqual(project.lag_days(link), 3)
        self.assertEqual(project.lag_days(link), link.lag)

    def test_a_percentage_is_a_share_of_the_predecessor(self):
        """
        Half of a five-day task is between two and three days.

        The share is of the task being waited for - "start this when that
        one is half done" is a statement about that one.
        """
        project = self.plan(lag=50, lag_unit='percent')
        link = project.get_task_by_id('second').dependencies[0]

        self.assertEqual(project.working_duration(
            project.get_task_by_id('first')), 5)
        self.assertEqual(project.lag_days(link), 3)      # 5 * 50%, rounded

    def test_a_percentage_of_nothing_delays_nothing(self):
        """A link whose predecessor has gone must not stop the redraw."""
        project = self.plan(lag=50, lag_unit='percent')
        link = project.get_task_by_id('second').dependencies[0]
        link.task_id = 'vanished'

        self.assertEqual(project.lag_days(link), 0)

    def test_the_unit_reaches_the_critical_path_cache_key(self):
        """
        Or a plan whose lag changed only in unit would keep the old answer.

        The analysis is cached against a signature of the plan and the chart
        asks for it on every redraw, so a signature that cannot see a change
        hands back a stale float for as long as the window is open.
        """
        project = self.plan(lag=2)
        before = project._analysis_signature()

        project.get_task_by_id('second').dependencies[0].lag_unit = 'percent'

        self.assertNotEqual(project._analysis_signature(), before)

    def test_the_unit_survives_an_undo_snapshot(self):
        """
        The structure snapshot copies every link.

        A copy that dropped the unit would turn a share into that many days
        the first time anything was undone.
        """
        project = self.plan(lag=50, lag_unit='percent')

        _order, _parents, links = project.structure_snapshot()

        self.assertEqual(links['second'][0].lag_unit, 'percent')

    def test_the_unit_survives_being_copied(self):
        """The clipboard rebuilds a task from a dictionary."""
        from gantt_app.utils.copypastecut import ClipboardService

        project = self.plan(lag=50, lag_unit='percent')
        data = project.get_task_by_id('second').to_dict()

        rebuilt = ClipboardService(project)._dict_to_task(data)

        self.assertEqual(rebuilt.dependencies[0].lag_unit, 'percent')

    def test_half_a_task_rounds_the_way_people_expect(self):
        """
        Half of five days is three, not two.

        Python's round() rounds half to even, so half a five-day task came
        out as two days and half a seven-day task as four - a rule nobody
        would guess at and not one worth explaining.
        """
        project = self.plan(lag=50, lag_unit='percent')
        link = project.get_task_by_id('second').dependencies[0]

        self.assertEqual(project.lag_days(link), 3)

    def test_a_negative_share_rounds_the_same_way(self):
        """Away from zero in both directions, or a lead is not a mirror."""
        project = self.plan(lag=-50, lag_unit='percent')
        link = project.get_task_by_id('second').dependencies[0]

        self.assertEqual(project.lag_days(link), -3)

if __name__ == '__main__':
    unittest.main()

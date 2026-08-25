"""
Tests for the formatting group on the icon bar.

WHY THIS MODULE EXISTS:
======================
The controls are simple; what they mean for a selection is not. "Is bold on"
has no single answer when three of five selected rows are bold, and getting it
wrong is invisible until somebody presses B on a mixed selection and watches
two rows lose their formatting instead of three rows gaining it.

So most of this is about the selection: what the bar shows for one, what it
shows for several that disagree, and that pressing a control means the same
thing in both cases.

The rest pins down the two promises made about the group itself - that it is
set apart from the row on both sides, and that every control in it says what
it is on hover.

DEVELOPMENT NOTES:
------------------
The module skips without a display; CI provides one through xvfb. The controls
are exercised through the handlers the buttons call, which needs no event loop
and tests the same code a press reaches.
"""

import unittest
from datetime import datetime, timedelta

from gantt_app.models import Project, Task
from gantt_app.taskstyle import PRESETS, TaskStyle

BASE = datetime(2026, 7, 6)


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
class StyleBarTestCase(unittest.TestCase):
    """A toolbar over a plan, with a task list wired to it."""

    def setUp(self):
        """Build the window, the toolbar and the list."""
        import customtkinter as ctk

        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )
        from gantt_app.views.task_list import DragDropTaskList
        from gantt_app.views.toolbar import Toolbar

        self.root = ctk.CTk()
        self.root.withdraw()

        self.project = Project(name="Plan")
        self.project.add_task(Task(id="P1", name="Phase", task_type="Phase",
                                   start_date=BASE,
                                   end_date=BASE + timedelta(days=10)))
        for task_id in ("T1", "T2"):
            self.project.add_task(Task(
                id=task_id, name=task_id, task_type="Task",
                parent_task_id="P1", start_date=BASE,
                end_date=BASE + timedelta(days=2)))

        self.manager = UndoRedoManager()
        self.toolbar = Toolbar(self.root, self.project,
                               undo_redo_manager=self.manager)
        self.task_list = DragDropTaskList(
            self.root, self.project,
            project_tracker=ProjectStateTracker(self.project, self.manager))
        self.toolbar.set_task_list(self.task_list)
        self.root.update()

        self.bar = self.toolbar.icon_toolbar.style_bar

    def tearDown(self):
        """Close the window."""
        try:
            self.root.destroy()
        except Exception:
            pass

    def select(self, *task_ids):
        """Select rows, and let the toolbar hear about it."""
        self.task_list.tree.selection_set(task_ids)
        self.root.update()

    def style(self, task_id: str) -> TaskStyle:
        """The formatting one task now carries."""
        return self.project.get_task_by_id(task_id).style


class TestTheGroupIsSetApart(StyleBarTestCase):
    """It changes how the plan is drawn, not what the plan says."""

    def test_it_sits_between_two_dividers(self):
        """
        Wedged against the buttons that indent and outdent, the B would
        read as another action on the task rather than a new group.
        """
        icons = self.toolbar.icon_toolbar
        children = icons.winfo_children()

        position = children.index(self.bar)
        neighbours = (children[position - 1], children[position + 1])

        for neighbour in neighbours:
            self.assertIn(neighbour, icons.separators)

    def test_it_follows_the_row_actions(self):
        """Formatting a row comes after the actions that change one."""
        self.assertEqual(self.toolbar.icon_toolbar.STYLE_GROUP_AFTER,
                         'outdent')

    def test_every_control_says_what_it_is(self):
        """A group of unlabelled letters and glyphs, otherwise."""
        from gantt_app.views.tooltip import Tooltip

        for name, button in self.bar.buttons.items():
            attached = getattr(button, 'tooltip_widget', None)
            self.assertIsInstance(attached, Tooltip, name)
            self.assertTrue(attached.text.strip(), name)

    def test_the_hotkeys_are_named_in_the_captions(self):
        """
        Somewhere a reader will actually look for them.

        Named with this platform's modifier: a hover promising Ctrl+B on a
        Mac names a key that does nothing there.
        """
        from gantt_app.shortcuts import accelerator

        for name, letter in (('bold', 'B'), ('italic', 'I'),
                             ('underline', 'U')):
            self.assertIn(accelerator(letter), self.bar.CAPTIONS[name])

    def test_the_group_holds_every_control_the_spec_names(self):
        """Three toggles, two colours, the presets and the way back."""
        self.assertEqual(list(self.bar.buttons), [
            'bold', 'italic', 'underline', 'text_color', 'fill_color',
            'style_preset', 'clear_style',
        ])


class TestItFollowsTheSelection(StyleBarTestCase):
    """Live when there is something to format, and not before."""

    def test_nothing_selected_leaves_it_disabled(self):
        """
        A bar that looks live with nothing to format invites a press that
        does nothing, and teaches the reader that it is unreliable.
        """
        self.select()

        self.assertFalse(self.bar.enabled)
        self.assertEqual(str(self.bar.buttons['bold'].cget('state')),
                         'disabled')

    def test_selecting_a_row_wakes_it_up(self):
        """Every control, not just the toggles."""
        self.select('T1')

        self.assertTrue(self.bar.enabled)
        for name, button in self.bar.buttons.items():
            self.assertEqual(str(button.cget('state')), 'normal', name)

    def test_a_disabled_control_applies_nothing(self):
        """Belt and braces: the handler refuses as well as the widget."""
        self.select()

        self.bar._apply('bold', True)

        self.assertTrue(self.style('T1').is_default)

    def test_it_shows_what_the_selected_row_carries(self):
        """So the toggle says what pressing it would undo."""
        self.project.get_task_by_id('T1').style = TaskStyle(italic=True)
        self.select('T1')

        self.assertTrue(self.bar._italic_on)
        self.assertFalse(self.bar._bold_on)

    def test_a_summary_row_reads_as_bold_with_nothing_set(self):
        """It is bold on screen, so the button has to agree."""
        self.select('P1')

        self.assertTrue(self.bar._bold_on)


class TestSeveralRowsAtOnce(StyleBarTestCase):
    """What the bar says, and does, for a selection that disagrees."""

    def test_a_mixed_selection_reads_as_off(self):
        """
        Showing the first row's formatting would be a lie about the rest.

        Read as on, pressing B would turn bold off for the rows that had it
        rather than on for the rows that did not.
        """
        self.project.get_task_by_id('T1').style = TaskStyle(bold=True)
        self.select('T1', 'T2')

        self.assertFalse(self.bar._bold_on)

    def test_pressing_it_then_applies_to_every_row(self):
        """Which is what the reader means by pressing it."""
        self.project.get_task_by_id('T1').style = TaskStyle(bold=True)
        self.select('T1', 'T2')

        self.bar._toggle('bold')

        self.assertTrue(self.style('T1').bold)
        self.assertTrue(self.style('T2').bold)

    def test_all_of_them_on_reads_as_on(self):
        """And pressing it then turns the emphasis off."""
        for task_id in ('T1', 'T2'):
            self.project.get_task_by_id(task_id).style = TaskStyle(bold=True)
        self.select('T1', 'T2')
        self.assertTrue(self.bar._bold_on)

        self.bar._toggle('bold')

        self.assertFalse(self.style('T1').bold)
        self.assertFalse(self.style('T2').bold)

    def test_a_colour_reaches_every_selected_row(self):
        """Highlighting is applied to a selection, not to a row at a time."""
        self.select('T1', 'T2')

        self.toolbar.apply_task_style('fill_color', '#fff2cc')

        self.assertEqual(self.style('T1').fill_color, '#fff2cc')
        self.assertEqual(self.style('T2').fill_color, '#fff2cc')

    def test_a_shared_colour_shows_on_the_indicator(self):
        """What pressing the button again would apply."""
        self.select('T1', 'T2')
        self.toolbar.apply_task_style('text_color', '#c0392b')

        self.assertEqual(str(self.bar.indicators['text_color'].cget('fg_color')),
                         '#c0392b')

    def test_colours_that_disagree_show_as_none(self):
        """There is no honest single colour to show."""
        self.project.get_task_by_id('T1').style = TaskStyle(fill_color='#fff2cc')
        self.project.get_task_by_id('T2').style = TaskStyle(fill_color='#d6eaf8')
        self.select('T1', 'T2')

        self.assertNotEqual(
            str(self.bar.indicators['fill_color'].cget('fg_color')), '#fff2cc')


class TestThePresetsAndTheWayBack(StyleBarTestCase):
    """One press to mark a row up, one to take it all off."""

    def test_a_preset_applies_its_whole_look(self):
        """Which is the point of having them."""
        self.select('T1')

        self.toolbar.apply_task_style('preset', dict(PRESETS)['Financial Milestone'])

        style = self.style('T1')
        self.assertEqual(style.fill_color, '#fff2cc')
        self.assertTrue(style.bold)

    def test_reset_puts_a_row_back_to_the_grid_default(self):
        """In one press, from whatever it was."""
        self.project.get_task_by_id('T1').style = TaskStyle(
            text_color='#c0392b', fill_color='#fff2cc', bold=True,
            italic=True, underline=True)
        self.select('T1')

        self.toolbar.apply_task_style('reset', None)

        self.assertTrue(self.style('T1').is_default)

    def test_reset_leaves_a_summary_bold(self):
        """
        Default formatting for a summary is bold, not plain.

        Clearing a phase's formatting must not make it look like a leaf.
        """
        from gantt_app.taskstyle import resolve

        self.project.get_task_by_id('P1').style = TaskStyle(text_color='#c0392b')
        self.select('P1')

        self.toolbar.apply_task_style('reset', None)

        self.assertTrue(resolve(self.style('P1'), is_summary=True).bold)


class TestItGoesThroughTheUndoHistory(StyleBarTestCase):
    """Marking rows up is a change to the plan like any other."""

    def test_formatting_can_be_undone(self):
        """It is stored on the task and saved with the file."""
        self.select('T1')
        self.toolbar.apply_task_style('bold', True)

        self.manager.undo()

        self.assertTrue(self.style('T1').is_default)

    def test_a_row_that_would_not_change_is_left_alone(self):
        """
        Applying the colour a row already has adds nothing to undo.

        Otherwise pressing the same swatch twice costs two undo steps and
        the second one appears to do nothing.
        """
        self.select('T1')
        self.toolbar.apply_task_style('fill_color', '#fff2cc')
        depth = len(self.manager.undo_stack)

        self.toolbar.apply_task_style('fill_color', '#fff2cc')

        self.assertEqual(len(self.manager.undo_stack), depth)


class TestTheHotkeys(StyleBarTestCase):
    """The formatting shortcuts, from wherever the focus is."""

    def test_all_three_are_bound_on_the_window(self):
        """
        Bound to a widget, they would stop working once a row is clicked.

        Matched on the key rather than on the modifier, because Tk stores a
        binding under its own spelling and that spelling is not the one it
        was given: <Command-b> comes back as <Mod1-Key-b> on a Mac. Which
        modifier goes into the sequence is pinned exactly in
        test_shortcuts.py; what matters here is that all three arrived.
        """
        bound = self.root.bind()

        for letter in ('b', 'i', 'u'):
            self.assertTrue(
                any(sequence.endswith(f'-Key-{letter}>') for sequence in bound),
                f"nothing bound for {letter}")

    def test_both_cases_are_bound(self):
        """
        Tk reports the upper case one when caps lock is on.

        A shortcut that stops working with caps lock is the kind of fault
        nobody reports and everybody notices.
        """
        bound = self.root.bind()

        for letter in ('B', 'I', 'U'):
            self.assertTrue(
                any(sequence.endswith(f'-Key-{letter}>') for sequence in bound),
                f"nothing bound for {letter}")

    def test_the_hotkey_toggles_the_selected_rows(self):
        """The same path the button takes."""
        self.select('T1')

        self.toolbar._hotkey_style('bold')

        self.assertTrue(self.style('T1').bold)

    def test_it_does_nothing_with_nothing_selected(self):
        """And does not raise on the way."""
        self.select()

        self.assertEqual(self.toolbar._hotkey_style('bold'), 'break')
        self.assertTrue(self.style('T1').is_default)


if __name__ == '__main__':
    unittest.main()

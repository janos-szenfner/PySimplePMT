"""
Tests for the formatting a row carries, and the defaults folded into it.

WHY THIS MODULE EXISTS:
======================
Two things here are easy to get wrong and invisible when they are.

The first is the three-valued emphasis. A summary row is bold without anybody
asking, so a plain True/False could not tell that automatic bold from one
somebody chose - and the consequences show up two steps away: pressing B on a
summary would appear to do nothing, and clearing a row's formatting would
leave a summary looking like a leaf.

The second is what a default style serialises to. Almost every row in almost
every plan carries no formatting, so a style that wrote five nulls per task
would grow every saved file for nothing.

Nothing here needs a display.
"""

import unittest

from gantt_app.taskstyle import (
    FILL_COLOURS, PRESETS, TEXT_COLOURS, TaskStyle, normalise_colour, resolve,
)


class ColourTestCase(unittest.TestCase):
    """What counts as a colour."""

    def test_a_six_digit_hex_is_kept(self):
        """The form everything downstream expects."""
        self.assertEqual(normalise_colour('#FFF2CC'), '#fff2cc')

    def test_a_missing_hash_is_added(self):
        """Colour pickers hand back both forms."""
        self.assertEqual(normalise_colour('fff2cc'), '#fff2cc')

    def test_the_short_form_is_expanded(self):
        """'#abc' is CSS for '#aabbcc' and people type it."""
        self.assertEqual(normalise_colour('#abc'), '#aabbcc')

    def test_nonsense_becomes_no_colour(self):
        """
        Rather than raising.

        These arrive from saved files. A plan that will not open because one
        row carried a damaged colour would be a bad trade for a row drawn in
        the default ink.
        """
        for value in ('', '   ', 'red', '#12345', '#gggggg', None, 42, []):
            self.assertIsNone(normalise_colour(value), repr(value))


class StyleTestCase(unittest.TestCase):
    """The style a task carries."""

    def test_a_new_style_is_the_default(self):
        """Nothing set, nothing to save."""
        self.assertTrue(TaskStyle().is_default)
        self.assertIsNone(TaskStyle().to_dict())

    def test_only_what_is_set_is_written(self):
        """Five nulls per task would grow every file for nothing."""
        self.assertEqual(TaskStyle(bold=True).to_dict(), {'bold': True})

    def test_a_style_survives_a_round_trip(self):
        """Everything set comes back the same."""
        style = TaskStyle(text_color='#c0392b', fill_color='#fff2cc',
                          bold=True, italic=False, underline=True)

        self.assertEqual(TaskStyle.from_any(style.to_dict()), style)

    def test_anything_unreadable_reads_as_the_default(self):
        """A plan saved before formatting existed opens with plain rows."""
        for value in (None, {}, 'nonsense', 7, []):
            self.assertTrue(TaskStyle.from_any(value).is_default, repr(value))

    def test_colours_are_normalised_on_the_way_in(self):
        """Whatever form they arrived in."""
        self.assertEqual(TaskStyle(text_color='C0392B').text_color, '#c0392b')

    def test_a_style_is_a_value(self):
        """
        Two rows formatted the same way hold equal styles.

        The task list shares one Tk tag between rows that resolve the same
        way, which is what makes a plan with forty marked rows configure one
        tag rather than forty.
        """
        self.assertEqual(TaskStyle(bold=True), TaskStyle(bold=True))
        self.assertEqual(len({TaskStyle(bold=True), TaskStyle(bold=True)}), 1)

    def test_changing_one_leaves_the_original_alone(self):
        """It is frozen, so a change is a new style."""
        original = TaskStyle(bold=True)

        changed = original.with_changes(italic=True)

        self.assertTrue(changed.italic)
        self.assertIsNone(original.italic)


class ResolvingTestCase(unittest.TestCase):
    """Folding a row's defaults into the formatting it carries."""

    def test_a_summary_is_bold_without_being_asked(self):
        """What makes an outline readable at a glance."""
        self.assertTrue(resolve(TaskStyle(), is_summary=True).bold)

    def test_a_leaf_is_not(self):
        """Bold everywhere is bold nowhere."""
        self.assertFalse(resolve(TaskStyle(), is_summary=False).bold)

    def test_a_summary_can_be_un_bolded_on_purpose(self):
        """
        The whole reason the flag is three-valued.

        With a plain False meaning "not set", a summary could never be
        anything but bold and the B would be a button that did nothing.
        """
        self.assertFalse(resolve(TaskStyle(bold=False), is_summary=True).bold)

    def test_clearing_a_summary_returns_it_to_bold(self):
        """Default formatting for a summary row is bold, not plain."""
        self.assertTrue(resolve(TaskStyle(), is_summary=True).bold)

    def test_the_other_two_are_off_unless_asked_for(self):
        """Nothing is italic or underlined by default, at any level."""
        for summary in (True, False):
            resolved = resolve(TaskStyle(), is_summary=summary)
            self.assertFalse(resolved.italic)
            self.assertFalse(resolved.underline)

    def test_colours_pass_straight_through(self):
        """There is no default ink or fill; the grid supplies those."""
        resolved = resolve(TaskStyle(text_color='#c0392b'), is_summary=True)

        self.assertEqual(resolved.text_color, '#c0392b')
        self.assertIsNone(resolved.fill_color)

    def test_nothing_at_all_resolves(self):
        """A task with no style is the ordinary case, not an error."""
        self.assertFalse(resolve(None).bold)


class PalettesTestCase(unittest.TestCase):
    """What the formatting bar offers."""

    def test_every_offered_colour_is_usable(self):
        """A swatch Tk cannot parse is a swatch that paints nothing."""
        for name, value in TEXT_COLOURS + FILL_COLOURS:
            self.assertTrue(name, "every swatch needs a name to hover")
            if value is not None:
                self.assertEqual(normalise_colour(value), value, name)

    def test_both_palettes_offer_a_way_back(self):
        """The default ink and no fill at all are choices too."""
        self.assertIn(None, [value for _name, value in TEXT_COLOURS])
        self.assertIn(None, [value for _name, value in FILL_COLOURS])

    def test_the_presets_are_the_four_the_spec_names(self):
        """One press each, because two menus and three toggles is not."""
        self.assertEqual([name for name, _style in PRESETS], [
            'Financial Milestone', 'Deliverable Complete',
            'Phase Gate / Approval', 'Summary Phase',
        ])

    def test_the_financial_preset_is_yellow_and_bold(self):
        """The one a payment milestone is marked with."""
        style = dict(PRESETS)['Financial Milestone']

        self.assertEqual(style.fill_color, '#fff2cc')
        self.assertTrue(style.bold)

    def test_the_approval_preset_is_red_bold_italic(self):
        """A phase gate has to stop the eye."""
        style = dict(PRESETS)['Phase Gate / Approval']

        self.assertEqual(style.text_color, '#c0392b')
        self.assertTrue(style.bold)
        self.assertTrue(style.italic)

    def test_every_preset_says_something(self):
        """A preset that resolves to the default would be a dead entry."""
        for name, style in PRESETS:
            self.assertFalse(style.is_default, name)


class TaskCarriesItTestCase(unittest.TestCase):
    """That the style reaches the model, and survives a saved file."""

    def task(self, **kwargs):
        """One task, with whatever is passed."""
        from datetime import datetime

        from gantt_app.models import Task

        options = dict(id='1', name='X', start_date=datetime(2026, 7, 6))
        options.update(kwargs)
        return Task(**options)

    def test_a_task_starts_with_no_formatting(self):
        """Which is what nearly every row in nearly every plan carries."""
        self.assertTrue(self.task().style.is_default)

    def test_a_plain_dictionary_is_accepted(self):
        """
        The importers, the undo history and every saved file hand one over.

        Coerced on assignment the way dependencies are, so no caller has to
        know that a style is its own type.
        """
        task = self.task()

        task.style = {'bold': True, 'fill_color': 'fff2cc'}

        self.assertIsInstance(task.style, TaskStyle)
        self.assertEqual(task.style.fill_color, '#fff2cc')

    def test_it_survives_being_saved_and_read_back(self):
        """The formatting travels with the plan, which is the point."""
        from gantt_app.models import Task

        task = self.task(style=TaskStyle(text_color='#c0392b', italic=True))

        self.assertEqual(Task.from_dict(task.to_dict()).style, task.style)

    def test_a_plan_saved_before_formatting_existed_still_opens(self):
        """With plain rows rather than an exception."""
        from gantt_app.models import Task

        data = self.task().to_dict()
        del data['style']

        self.assertTrue(Task.from_dict(data).style.is_default)

    def test_an_ordinary_edit_does_not_strip_it(self):
        """
        The undo tracker rebuilds a task from a list of fields.

        Anything missing from that list is reset to its default by any
        update at all - which is what was happening to calendar_id, and
        would have happened to the formatting the moment somebody renamed a
        row they had just marked up.
        """
        from datetime import datetime

        from gantt_app.models import Project, Task
        from gantt_app.utils.undoredo import (
            ProjectStateTracker, UndoRedoManager,
        )

        project = Project(name='P')
        project.add_task(Task(id='1', name='X',
                              start_date=datetime(2026, 7, 6),
                              calendar_id='weekend',
                              style=TaskStyle(bold=True)))
        tracker = ProjectStateTracker(project, UndoRedoManager())

        tracker.update_task('1', name='Renamed')

        task = project.get_task_by_id('1')
        self.assertEqual(task.style, TaskStyle(bold=True))
        self.assertEqual(task.calendar_id, 'weekend')


if __name__ == '__main__':
    unittest.main()

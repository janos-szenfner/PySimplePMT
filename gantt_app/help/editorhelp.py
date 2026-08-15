"""
The reference window behind the task editor's Help button.

WHY THIS MODULE EXISTS:
======================
The editor asks for a type, two dates, a milestone flag and a percentage, and
what those mean to the chart is not obvious from the form: whether a task
needs an end date, why ticking Milestone empties one, what a sub-task does to
its parent's dates. The form has no room to say, and the answers do not change
often enough to belong on it.

The window follows the Dependency tab's, which answers the same kind of
question about links.

DEVELOPMENT NOTES:
------------------
Content only. The window itself is ReferenceWindow, shared with the
dependency reference - see gantt_app/help/reference.py.

The sections follow the order of the fields on the General tab, so someone
looking at a box on the form finds it in the same place here.
"""

from gantt_app.help.reference import ReferenceWindow


#: The reference text, as (heading, [paragraph, ...]).
#:
#: Written for this application: the names match the fields on the General
#: tab, and the worked examples use its inclusive end dates.
HELP_SECTIONS = (
    (
        "Tasks",
        [
            "A task is a piece of work with a start and an end. It is drawn "
            "on the chart as a horizontal bar whose length is its duration, "
            "so the plan can be read at a glance.",

            "Tasks may run one after another or side by side. Nothing stops "
            "two bars overlapping - independent work happening at the same "
            "time is what that looks like. Use the Dependency tab when one "
            "task genuinely has to wait for another, rather than typing dates "
            "that happen to fall in the right order.",
        ],
    ),
    (
        "Sub-tasks",
        [
            "A sub-task is a task belonging to another one. Its parent is "
            "shown on the form and cannot be changed here; use Indent and "
            "Outdent on the right-click menu to move a task in or out.",

            "A task with sub-tasks brackets them rather than holding work of "
            "its own. Its dates come from its children - the earliest start "
            "and the latest finish - and its progress is their average, "
            "weighted by how long each one lasts, so editing the dates of a "
            "task that has sub-tasks has no lasting effect.",
        ],
    ),
    (
        "Milestones",
        [
            "A milestone marks a moment rather than a span of work: design "
            "approved, MVP released, client sign-off. It takes no time, so it "
            "has no end date, and ticking Is Milestone empties that box and "
            "greys it out. Un-ticking gives it back.",

            "Because a milestone occupies no day, a task that follows one on "
            "the 15th starts on the 15th, not the 16th.",

            "Milestones are drawn as a marker instead of a bar, which is what "
            "makes them stand out when the plan is shown to somebody who did "
            "not write it.",
        ],
    ),
    (
        "Start date, end date and duration",
        [
            "Dates are written as YYYY-MM-DD - 2026-08-15. The button beside "
            "each box opens a calendar, which fills it in correctly whatever "
            "the local date convention is.",

            "End dates cover the whole of their day. A task running from the "
            "1st to the 5th lasts five days, and the Duration field counts it "
            "that way.",

            "The form points out a date it cannot read, or a required one "
            "left empty, as you type. It says so beneath the fields rather "
            "than waiting for Save, so a mistyped date is caught while you "
            "are still looking at it.",
        ],
    ),
    (
        "% Completion",
        [
            "Progress runs from 0 to 100 and shades that much of the task's "
            "bar, so how far along a task is can be read against the line "
            "marking today: a bar less shaded than it should be by now is "
            "behind.",

            "Progress on a task with sub-tasks is not entered - it is the "
            "average of theirs, weighted by duration.",
        ],
    ),
    (
        "Colour",
        [
            "Colour carries no meaning to the application: nothing is "
            "scheduled, grouped or exported differently because of it. It is "
            "there to let a reader tell work streams apart - one colour per "
            "team, per phase, or per whatever the plan is organised around.",

            "New rows start on a colour chosen by what they are, so tasks, "
            "sub-tasks and milestones are already distinguishable before "
            "anybody picks anything.",
        ],
    ),
    (
        "The timeline",
        [
            "The chart's horizontal axis can be shown by day, week or month, "
            "and the zoom controls move between them: in for the detail of a "
            "fortnight, out for the shape of a year.",

            "A vertical line marks today, which is what the shading on each "
            "bar is read against.",
        ],
    ),
)


class EditorHelpWindow(ReferenceWindow):
    """
    A scrollable reference on the task editor's fields.

    DEVELOPMENT NOTES:
    ------------------
    Everything but the words is in ReferenceWindow, which the Dependency
    tab's Help button shares. Not modal, so it can be read while the editor
    is open behind it - which is the whole point of a Help button on a form.
    """

    TITLE = "Task Editor - Help"
    GEOMETRY = "720x640"
    SECTIONS = HELP_SECTIONS

    #: This window's own; the dependency reference keeps a separate one.
    _open_window = None

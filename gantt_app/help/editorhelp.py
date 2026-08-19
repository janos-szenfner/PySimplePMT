"""
The reference window behind the task editor's Help button.

WHY THIS MODULE EXISTS:
======================
The editor asks for a type, two dates, a duration, a scheduling mode, a
calendar, a milestone flag and a percentage, and what those mean to the plan
is not obvious from the form: which of the three date fields is being worked
out for you, why a finish lands where it does, which days count as worked,
why ticking Milestone empties a box, what a sub-task does to its parent's
dates. The form has no room to say, and the answers do not change often
enough to belong on it.

It answers all of it: every field on the form, how the calculated one is
worked out, which days the calendar counts as worked and why a task moved
after being saved. The Dependency tab keeps its own reference, which answers
the same kind of question about links.

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
        "What this form is",
        [
            "Everything the plan knows about one row. The General tab holds "
            "what it is, when it happens and how it is drawn; the Dependency "
            "tab holds what it waits for, and has a Help button of its own.",

            "Every section below is named after a field on the form, in the "
            "order the fields appear, so a box you are looking at is found in "
            "the same place here. Use the search box at the top: it matches "
            "any word or number, Enter walks the hits and Escape clears it.",
        ],
    ),
    (
        "Type: the levels of a plan",
        [
            "Phase - the outermost grouping, a stage of the project. A "
            "container: it holds no work of its own, and its dates and "
            "progress come from what is inside it.",

            "Deliverable - a thing that gets handed over. Also a container, "
            "and also takes its dates from its children.",

            "Task - the primary unit of work. This is the level that holds a "
            "duration, a start, a finish and a percentage complete.",

            "Subtask - a step inside a task, for tracking completion at a "
            "finer grain than the task itself.",

            "Milestone - a moment rather than a stretch of work. No duration "
            "and no finish; it marks a date.",

            "A sub-task cannot change its type or its parent from this form. "
            "Use Indent and Outdent in the list instead, which move a row "
            "and settle its type in one action.",

            "A row keeps its own type wherever the new parent can hold it: a "
            "Task indented under a Deliverable stays a Task, and so can still "
            "hold sub-tasks. Only a type the parent cannot hold is changed - "
            "a Task under another Task becomes a Subtask.",
        ],
    ),
    (
        "Tasks",
        [
            "A task is a piece of work with a start and an end. It is drawn "
            "on the chart as a horizontal bar across the days it spans, so "
            "the plan can be read at a glance.",

            "Tasks may run one after another or side by side. Nothing stops "
            "two bars overlapping - independent work happening at the same "
            "time is what that looks like. Use the Dependency tab when one "
            "task genuinely has to wait for another, rather than typing dates "
            "that happen to fall in the right order.",
        ],
    ),
    (
        "Sub-tasks and containers",
        [
            "A sub-task is a task belonging to another one. Its parent is "
            "shown on the form and cannot be changed here.",

            "A row with children brackets them rather than holding work of "
            "its own. Its dates come from its children - the earliest start "
            "and the latest finish - and its progress is theirs, so editing "
            "the dates of a row that has children has no lasting effect: the "
            "next reschedule takes them from the children again.",

            "That is also why the Duration box is filled in but not yours to "
            "type in on a Phase or a Deliverable. The number shown is what "
            "the children span, reported rather than stored.",
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

            "Milestones are drawn as a diamond instead of a bar, which is "
            "what makes them stand out when the plan is shown to somebody "
            "who did not write it.",
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
            "that way. A one-day task finishes on the day it starts.",

            "Duration is *working* effort, not elapsed time - see the two "
            "sections below. It is the number that stays the same when a task "
            "crosses a weekend.",

            "The form points out a date it cannot read, or a required one "
            "left empty, as you type. It says so beneath the fields rather "
            "than waiting for Save, so a mistyped date is caught while you "
            "are still looking at it.",
        ],
    ),
    (
        "Scheduling options: which field is calculated",
        [
            "The start, the finish and the duration describe the same thing "
            "twice over, so one of them is always worked out from the other "
            "two. This menu says which, and the calculated box is shaded to "
            "show it is not yours to type in.",

            "End date is calculated - you give the start and the duration, "
            "and the finish follows. The usual choice, and the default.",

            "Start date is calculated - you give the finish and the duration, "
            "and the start is worked back from it. For work that has to be "
            "finished by a date.",

            "Duration is calculated - you give both dates, and the working "
            "effort between them is counted.",

            "It updates live, as you type in the other two boxes. There is no "
            "need to save to see what the answer will be, and the answer "
            "shown is the one the scheduler will use.",
        ],
    ),
    (
        "How the end date is worked out",
        [
            "A finish is walked, not added. Starting at the start date, the "
            "calendar is stepped through one day at a time and one day of "
            "duration is spent only on a day that is worked.",

            "So a task reaching a weekend pauses on the Saturday and resumes "
            "on the Monday. It finishes further out on the wall calendar "
            "without holding any more work.",

            "Worked example: five days of work starting Thursday 3 September "
            "2026 finishes on Wednesday 9 September - seven calendar days "
            "later, because the Saturday and the Sunday are not worked. The "
            "Duration box still says five.",

            "This is why the two measurements are kept apart. Duration is the "
            "effort a task holds and does not change when it crosses a "
            "weekend; the bar on the chart is drawn across the elapsed days "
            "and does.",

            "A task cannot start on a day nobody works. One typed or dragged "
            "onto a Saturday starts on the Monday instead, and the finish is "
            "worked out from there.",
        ],
    ),
    (
        "How the working calendar decides",
        [
            "Which days count as worked is set in Actions > Calendar "
            "Settings, and is read in a strict order. The first rule that "
            "answers wins:",

            "1. A manual override on that exact date. Highest priority - "
            "nothing can overturn it. This is how a single Saturday is made a "
            "working day, or a Wednesday taken off for a shutdown.",

            "2. A public holiday in any country or region the plan observes. "
            "The union applies: a date that is a holiday in any of them is "
            "not worked.",

            "3. A holiday listed in the plan, or one that recurs every year - "
            "usually carried in from an imported file.",

            "4. The working week. Saturday and Sunday off unless the plan "
            "says otherwise.",

            "So a date named as a working day is worked even if it is a "
            "Saturday and a public holiday at once. Somebody typing that date "
            "into the overrides list could see what it was and meant it.",
        ],
    ),
    (
        "Working calendar: a task on its own",
        [
            "The Working calendar box picks which calendar this task is "
            "scheduled against. Project Default is the plan's own, which is "
            "what almost every task follows.",

            "A task may follow a different one - a weekend-only shift for "
            "work that can only touch production on a Saturday, a 24/7 "
            "calendar for something that runs unattended. Picking one "
            "re-dates the task immediately, before you save, so you can see "
            "where it lands.",

            "Worked example: a three-day task starting Thursday 10 September "
            "2026 runs to Monday 14 September on the standard week. On a "
            "weekend-only calendar it cannot begin on a Thursday at all, so "
            "it starts on Saturday 12 September. On a 24/7 calendar it runs "
            "10 to 12 September straight through.",

            "The box only appears when the plan has named calendars to "
            "choose from. New ones are made in Calendar Settings.",
        ],
    ),
    (
        "Earliest begin",
        [
            "A floor on when the work can start: material not delivered, a "
            "gate not passed, a contract not signed.",

            "It only ever pushes a task later, never earlier. A task whose "
            "links would have started it sooner waits; one that was already "
            "starting later is left alone.",

            "Tick the box to use it. Copy begin date fills it in from the "
            "start date already on the form.",
        ],
    ),
    (
        "% Completion",
        [
            "Progress runs from 0 to 100 and shades that much of the task's "
            "bar, so how far along a task is can be read against the line "
            "marking today: a bar less shaded than it should be by now is "
            "behind.",

            "Progress on a row with children is not entered - it is theirs, "
            "counted in the way that suits the level, so a phase of ten tasks "
            "is not dragged to 100% by one finished task.",

            "A milestone is either reached or not; it has no partial "
            "progress.",
        ],
    ),
    (
        "Priority",
        [
            "A label for the reader, and for sorting and filtering. It "
            "changes no dates: the scheduler places work by the calendar and "
            "the links, not by how important it is.",

            "If a high-priority task has to happen first, say so with a "
            "dependency or an earliest begin date. Priority alone will not "
            "move it.",
        ],
    ),
    (
        "Show in timeline, Shape and Colour",
        [
            "Show in timeline hides this row's bar from the chart without "
            "removing the row from the plan. Its dates still count towards "
            "its parent's, and anything depending on it still follows it.",

            "Shape changes how the bar is drawn. Colour carries no meaning "
            "to the application: nothing is scheduled, grouped or exported "
            "differently because of it. It is there to let a reader tell "
            "work streams apart - one colour per team, per phase, or per "
            "whatever the plan is organised around.",

            "New rows start on a colour chosen by what they are, so tasks, "
            "sub-tasks and milestones are already distinguishable before "
            "anybody picks anything.",
        ],
    ),
    (
        "Details",
        [
            "Free notes about the row. They travel with the plan, are saved "
            "with it, and appear in the exports that have somewhere to put "
            "them.",

            "Nothing in them is parsed. They are for the people reading the "
            "plan, not for the scheduler.",
        ],
    ),
    (
        "Dependencies",
        [
            "The Dependency tab is where one task is made to wait for "
            "another. It carries its own Help button covering the four link "
            "types, hardness, and lag and lead.",

            "In short: a link says which end of this task is held by which "
            "end of another, a Hard link pins the date exactly while a Soft "
            "one is only a floor, and a lag is a wait built into the link - "
            "counted in the project's working days.",
        ],
    ),
    (
        "Why a box is shaded",
        [
            "A shaded box is one the application is filling in, not one that "
            "is broken. Three things do it:",

            "The field the Scheduling options menu names as calculated. "
            "Change the menu and a different box becomes yours to type in.",

            "The end date of a milestone, which has none by definition.",

            "The duration of a Phase or a Deliverable, which is what its "
            "children span rather than a number of its own.",
        ],
    ),
    (
        "Why the dates moved after saving",
        [
            "Almost always one of four rules, in this order of likelihood:",

            "The start landed on a day nobody works and was moved to the next "
            "working day. Check the working week, the holidays and any "
            "override on that date.",

            "A dependency moved it. A Hard link pins a date exactly; check "
            "the Dependency tab for what this task follows and with what lag.",

            "An Earliest begin date is holding it. That is a floor and only "
            "ever pushes work later.",

            "It follows a calendar of its own. A weekend-only task cannot "
            "start on a Tuesday, whatever was typed.",

            "What never happens silently is the effort changing. A calendar "
            "change holds the duration and moves the finish, which is why a "
            "task can end later without holding any more work.",
        ],
    ),
    (
        "The timeline",
        [
            "The chart's horizontal axis shows as many dates as the window "
            "has room for, and the zoom controls below it move between the "
            "detail of a fortnight and the shape of a year. Fit returns to "
            "the whole plan.",

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
    GEOMETRY = "780x700"
    SECTIONS = HELP_SECTIONS

    #: Searchable, now that it is long enough to be looked things up in.
    #:
    #: It was not, and the reason was that a screen or two is faster read
    #: than searched. That was true of the seven short sections this used to
    #: be and is not true of the nineteen it now has - a reader wanting to
    #: know what shades a box should not have to scroll for it.
    SEARCHABLE = True

    #: This window's own; the dependency reference keeps a separate one.
    _open_window = None

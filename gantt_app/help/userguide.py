"""
The full user guide: every field, every rule, and how the dates are worked out.

WHY THIS MODULE EXISTS:
======================
Two short references already existed - one behind the task editor's Help
button, one behind the Dependency tab's - and both are deliberately narrow:
they explain the form the reader is looking at and nothing else. Neither
answers "what is a Deliverable", "why did my task move", "what does float
mean", or "which calendar is this task on", and those are the questions that
send somebody to the source code.

This is the whole of it in one window, opened by the ? on the icon bar or
View > Help, with a search box across the top - because a guide this long is
not read, it is looked things up in.

DEVELOPMENT NOTES:
------------------
The content is a plain data structure - (heading, [paragraph, ...]) - which is
what ReferenceWindow renders and what the search walks. Prose rather than
markup so it stays readable in the source, and written here rather than
fetched so the guide works with no network and nothing to download: the same
rule the rest of the application follows.

The numbers in the worked examples are real. Every date in here was produced
by the scheduler rather than typed from memory, because a guide that disagrees
with the application is worse than no guide - the reader believes it, and the
disagreement is only found much later. There is a test that re-derives them.
"""

from gantt_app.help.reference import ReferenceWindow


#: The guide, as (heading, [paragraph, ...]).
#:
#: Ordered the way somebody meets the application: what the pieces of a plan
#: are, then how to describe one, then how the dates are worked out, then the
#: things built on top of the dates, then getting plans in and out.
GUIDE_SECTIONS = (
    (
        "What this application is",
        [
            "A desktop planner: a task list on the left, a Gantt chart on "
            "the right, and one working-day calendar behind both. Everything "
            "is a plain file on your machine - nothing is uploaded and "
            "nothing needs a network.",

            "The two panes are one plan. Selecting, editing or reordering in "
            "the list moves the chart, and the divider between them can be "
            "dragged to give either side more room.",

            "Use the search box at the top of this window to find anything "
            "here: a field name, a rule, a number, a date. Enter walks "
            "through the hits, Shift+Enter walks back, Escape clears it.",
        ],
    ),
    (
        "The levels of a plan",
        [
            "Work is described at four levels, plus a marker that can sit at "
            "any of them:",

            "Phase - the outermost grouping. A stage of the project, holding "
            "deliverables and the work under them. It has no length of its "
            "own: its dates and its progress come from what is inside it.",

            "Deliverable - a thing that gets handed over. Also a container: "
            "its dates and progress come from its children.",

            "Task - the primary unit of work. This is what holds a duration, "
            "a start, a finish and a percentage complete.",

            "Subtask - a step inside a task, for tracking completion at a "
            "finer grain than the task itself.",

            "Milestone - a moment rather than a stretch of work. It has no "
            "duration and no finish; it marks a date. Drawn as a diamond.",

            "Only the levels that hold work - Task and Subtask - have "
            "durations you set. A Phase or a Deliverable showing a duration "
            "is reporting what its children span, not a number of its own.",
        ],
    ),
    (
        "Moving work between levels",
        [
            "Indent and outdent change a row's parent. A row keeps its own "
            "type wherever the new parent can hold it: a Task indented under "
            "a Deliverable stays a Task, and so can still hold subtasks of "
            "its own.",

            "Only a type the new parent cannot hold is changed. A Task under "
            "another Task becomes a Subtask; a Subtask lifted into a Phase "
            "becomes a Task. A Milestone stays a Milestone wherever it "
            "lands.",

            "Creating a row under a parent settles its type the same way, so "
            "indenting and creating always agree.",

            "Indenting and outdenting act on every selected row, not only "
            "the one under the pointer.",
        ],
    ),
    (
        "The task editor: identity",
        [
            "Name - what the row is called. Shown in the list and beside its "
            "bar on the chart.",

            "ID - assigned by the application and shown for reference. It is "
            "what dependencies and calendars point at internally.",

            "Type - Phase, Deliverable, Task, Subtask or Milestone. See the "
            "levels above. A sub-task cannot change its type or its parent "
            "from the editor; move it in the list instead.",

            "Parent - the row this one sits under. Empty for a top-level "
            "row.",

            "Details - free notes. They travel with the plan and appear in "
            "the exports that have somewhere to put them.",
        ],
    ),
    (
        "The task editor: dates and duration",
        [
            "Start date - when work begins. A start landing on a day nobody "
            "works is moved forward to the next working day; see the "
            "calendar sections below.",

            "End date - the last day worked, inclusive. A one-day task "
            "finishes on the day it starts.",

            "Duration (days) - working effort, not elapsed time. This is the "
            "number that stays the same when a task crosses a weekend.",

            "Is milestone - marks the row as a moment with no length. Its "
            "finish and duration stop applying.",

            "Earliest begin - a floor on when the work can start: material "
            "not delivered, a gate not passed. It only ever pushes a task "
            "later, never earlier.",

            "Working calendar - which calendar this task is scheduled "
            "against. See 'A task on its own calendar' below. The dropdown "
            "only appears when the plan has named calendars to choose from.",
        ],
    ),
    (
        "Scheduling options: which field is calculated",
        [
            "Three fields describe the same thing twice over - a start, a "
            "finish and a length - so one of them is always worked out from "
            "the other two. The Scheduling options menu says which:",

            "End date is calculated - you give the start and the duration, "
            "and the finish follows. The usual choice, and the default.",

            "Start date is calculated - you give the finish and the "
            "duration, and the start is worked back from it. For work that "
            "has to be finished by a date.",

            "Duration is calculated - you give both dates, and the effort "
            "between them is counted.",

            "The calculated field is shaded and filled in for you as you "
            "type in the other two. It updates live; there is no need to "
            "save to see what it will be.",
        ],
    ),
    (
        "Working days and calendar days",
        [
            "These are two different measurements and confusing them is what "
            "makes a schedule wrong over a weekend.",

            "Working days (the duration) - the effort a task holds. Five "
            "days of effort is five days of effort whether or not a Saturday "
            "falls in the middle of it.",

            "Calendar days (the elapsed span) - how far apart the two ends "
            "sit on a wall calendar. This is the span the chart draws.",

            "A finish is walked, not added. Starting at the start date, the "
            "calendar is stepped through a day at a time and one day of "
            "duration is spent only on a working day. So a task reaching a "
            "weekend pauses on the Saturday and resumes on the Monday, "
            "finishing further out in calendar time without holding any more "
            "work.",

            "Worked example: five days of work starting Thursday 3 September "
            "2026 finishes on Wednesday 9 September - seven calendar days "
            "later, because the Saturday and Sunday are not worked.",
        ],
    ),
    (
        "Which days are worked",
        [
            "Actions > Calendar Settings holds all of it, in three tabs. The "
            "rules are read in a strict order, and the first one that "
            "answers wins:",

            "1. A manual date override, if the date has one. Highest "
            "priority - nothing can overturn it.",

            "2. A public holiday in any country or region the plan observes.",

            "3. A listed or recurring holiday carried in from an imported "
            "file.",

            "4. The working week - by default Saturday and Sunday off.",

            "A task cannot start on a day nobody works. One scheduled or "
            "moved onto a Saturday starts on the Monday instead.",
        ],
    ),
    (
        "Calendar Settings: Working Week",
        [
            "Which weekdays are worked at all. Tick the days that ARE "
            "worked - a six-day week, a four-day week, or the standard "
            "Monday to Friday.",

            "Changing it holds every task's effort and moves its finish. "
            "Putting Saturday to work pulls finishes in rather than "
            "lengthening tasks: a four-day task running Friday 11 September "
            "2026 to Wednesday 16 September ends on Tuesday 15 September "
            "once Saturday is worked, still holding four days.",

            "A week with no working day in it is refused. The calendar would "
            "accept one and then treat every day as worked, which is the "
            "opposite of what was asked for.",
        ],
    ),
    (
        "Calendar Settings: National Holidays",
        [
            "Pick any of the ~250 countries the holidays package knows, and "
            "their regions - Bavaria's three extra holidays are observed "
            "rather than Germany's national list alone. A search box finds a "
            "country or region by name or code, and the 27 EU member states "
            "sit behind one button.",

            "The rule is the union: a date that is a public holiday in ANY "
            "selected country or region is a non-working day for the plan. "
            "That is what a project worked across several countries needs - "
            "work does not happen on a day half the team is off.",

            "Easter Monday and the other movable feasts are worked out per "
            "year, so a task spanning one is pushed out rather than losing "
            "the work planned for it. What is saved is the country codes, "
            "not the dates: a plan reopened in a later year gets that year's "
            "holidays.",
        ],
    ),
    (
        "Calendar Settings: Manual Overrides",
        [
            "For the dates no rule can describe: a Saturday being worked to "
            "make a deadline, or a shutdown week in August. An override is a "
            "date, a type - Working Day or Non-Working Day - and an optional "
            "reason for whoever reads the list back later.",

            "An override beats everything else, in both directions. A date "
            "named as worked is worked even if it is a Saturday and "
            "Christmas Day at once; an ordinary Tuesday named as "
            "non-working is not worked.",

            "A date can only be ruled on one way, so adding an override for "
            "a date that already has one replaces it. That is also how one "
            "is edited. Deleting an override puts the date back under the "
            "ordinary rules.",
        ],
    ),
    (
        "A task on its own calendar",
        [
            "A plan does not always run on one week. A migration that can "
            "only touch production at the weekend and a load test that runs "
            "around the clock are scheduled wrong by any single calendar.",

            "So calendars can be named, and a task can follow one instead of "
            "the plan's. Set it from the task editor's Working calendar "
            "dropdown; the task is re-dated the moment you pick one. Three "
            "come with every new plan - Standard Week, Weekend-Only Shift "
            "and 24/7 Continuous Run - and more can be built with New in "
            "Calendar Settings.",

            "Worked example. Three tasks of three days each, all starting "
            "Thursday 10 September 2026: on the plan's own Monday-to-Friday "
            "calendar it runs 10 to 14 September; on a weekend-only "
            "calendar it starts Saturday 12 September, because a Thursday is "
            "not a day it can begin on; on a 24/7 calendar it runs 10 to 12 "
            "September straight through.",

            "A task naming a calendar that has since been deleted quietly "
            "goes back to the plan's own, so removing a calendar never "
            "leaves a task without one.",
        ],
    ),
    (
        "Dependencies: the four link types",
        [
            "A link says one task's dates depend on another's. Set them on "
            "the Dependency tab of the task editor.",

            "Finish - Start (FS) - the successor starts after the "
            "predecessor finishes. The common one, and what most plans mean "
            "by 'depends on'.",

            "Start - Start (SS) - the two start together. For work that runs "
            "alongside something rather than after it.",

            "Finish - Finish (FF) - the two finish together. For work that "
            "has to be done by the time something else is.",

            "Start - Finish (SF) - the successor finishes when the "
            "predecessor starts. Rare; it describes a handover, where one "
            "thing stops as another begins.",
        ],
    ),
    (
        "Dependencies: hardness, lag and lead",
        [
            "Hardness - a Hard link pins the date exactly. A Soft link is a "
            "floor: it stops the successor starting too early but leaves any "
            "gap you have deliberately left alone.",

            "Lag - a wait built into the link, in working days. A "
            "Finish - Start link with a lag of 3 starts the successor three "
            "working days after the predecessor finishes: curing time, a "
            "delivery, an approval.",

            "A negative lag is lead time. It lets the successor begin before "
            "the predecessor is done, so the two overlap by that much - "
            "which is how a schedule is compressed without pretending the "
            "work takes less time.",

            "Lag is counted in the PROJECT's working days, even where either "
            "task follows a calendar of its own. It is a number typed onto a "
            "link and it has to mean one thing: counted on the successor's "
            "week, the same lag of 2 would be two days for an ordinary task "
            "and eight calendar days for one on a weekend-only shift. The "
            "successor's own calendar still decides where it may start once "
            "the wait is over.",

            "A task cannot depend on itself, on its own subtasks, or in a "
            "circle.",
        ],
    ),
    (
        "Critical path and float",
        [
            "Actions > Critical Path analyses the plan both ways round and "
            "reports, for every task, how much it could slip before the "
            "project finishes later.",

            "Total float - working days of slack. Zero means the task cannot "
            "slip at all, so it is on the critical path. Every zero-float "
            "task is listed, not one chain through them, so parallel work "
            "that is equally critical shows up as such.",

            "Negative float is reported rather than hidden. It means the "
            "links contradict each other - a task required to finish before "
            "something it also has to follow - and that is a plan that "
            "cannot be delivered as drawn, which is worth seeing.",

            "Float is counted in the PROJECT calendar's working days, "
            "including for tasks that follow a calendar of their own, so "
            "every task is measured against the same ruler. Measured against "
            "its own week, a task would sit at a different number for the "
            "same day and slack between two tasks on different calendars "
            "would come out as the difference between their calendars.",
        ],
    ),
    (
        "Progress and roll-up",
        [
            "Progress (%) is set on the rows that hold work. Containers - "
            "Phase and Deliverable - do not take a number of their own: they "
            "report what is under them.",

            "Each level counts what is under it in the way that suits that "
            "level, so a phase of ten tasks is not dragged to 100% by one "
            "finished task, and a task with subtasks reflects how many of "
            "them are done.",

            "A milestone is either reached or not; it has no partial "
            "progress.",
        ],
    ),
    (
        "The chart",
        [
            "Bars are drawn across the calendar span - the elapsed days - so "
            "a task crossing a weekend reaches further than its duration "
            "suggests. That difference is the point of the two "
            "measurements.",

            "A Phase is drawn as a pointed bar bracketing what is inside it. "
            "A Milestone is a diamond. Dependencies are drawn as arrows "
            "between the rows they link.",

            "Show in timeline hides a row's bar without removing the row "
            "from the plan.",

            "Shape and Colour set how a bar is drawn. View > Settings holds "
            "the chart-wide options; the zoom controls and Fit are under the "
            "chart itself.",

            "The chart opens framed on the plan: one day of calendar before "
            "the first bar and enough after the last for its label. Use Fit "
            "to return to that framing after zooming.",
        ],
    ),
    (
        "Day and Night",
        [
            "The window follows your desktop's light or dark setting and "
            "keeps following it - if the system switches at sunset, so does "
            "the window.",

            "The Day / Night button on the icon bar flips it by hand and "
            "detaches from the desktop. Sync with system appears beside it "
            "only while that manual choice is in force, and puts it back.",

            "The same three modes are under View > System UI mode. The "
            "choice is remembered between runs.",
        ],
    ),
    (
        "Editing: undo, copy and paste",
        [
            "Undo and Redo cover the editing actions: creating, deleting, "
            "moving, renaming and re-dating rows.",

            "Cut, Copy and Paste move rows about, including into and out of "
            "containers. A row cannot be pasted inside itself.",

            "Calendar changes are not on the undo stack. Changing a "
            "calendar setting back moves the plan back, which is how that "
            "change is undone.",
        ],
    ),
    (
        "Files: saving and opening",
        [
            "Project > Save and Project > Load use this application's own "
            "JSON format, which carries everything: the tasks, the links, "
            "the calendars, the overrides and the per-task calendar "
            "assignments.",

            "A plan saved by an older version opens in a newer one. Anything "
            "the older version did not have is simply absent rather than "
            "wrong - a file written before named calendars existed opens "
            "with none, and every task in it follows the project's own.",
        ],
    ),
    (
        "Files: importing",
        [
            "File > Import reads four formats.",

            "GAN - GanttProject files. The file's own calendar block is "
            "replayed, so the imported plan keeps the weekend definition and "
            "the holidays that file declared and shows the dates "
            "GanttProject showed.",

            "XLSX - spreadsheets. Reads cached formula results, so a "
            "workbook saved without a calculation pass has empty date "
            "columns; rows carrying a duration and predecessors are "
            "rescheduled from the plan's start date instead.",

            "Mermaid - gantt diagrams. What the diagram syntax cannot hold "
            "travels in a comment line, so a plan exported and reimported "
            "comes back as it went in.",

            "MPP - Microsoft Project files. Needs the optional Tasklib "
            "package and is not part of the packaged build.",
        ],
    ),
    (
        "Files: exporting",
        [
            "File > Export writes Mermaid, HTML, SVG, PNG, PDF and XLSX.",

            "The XLSX export is a live sheet, not a picture. Duration is a "
            "number you can change, and Start and End are WORKDAY formulas "
            "over it, so re-planning in Excel behaves the way re-planning "
            "here does.",

            "A formula is only written where it reproduces the date this "
            "application already worked out. Where a WORKDAY chain could not "
            "say what the plan says - a Start-Start link, a lag, or a "
            "Saturday the plan works and Excel's fixed Monday-to-Friday week "
            "cannot - the real date is written instead. A sheet that is live "
            "but wrong would be worse than one that is merely static.",

            "PDF and PNG export the chart as drawn.",
        ],
    ),
    (
        "When something moves and you did not move it",
        [
            "Almost always one of four rules, in this order of likelihood:",

            "A start landed on a non-working day and was pushed to the next "
            "working one. Check the working week, the holidays, and any "
            "override on that date.",

            "A dependency moved it. A hard link pins a date exactly; check "
            "the Dependency tab for what it follows and with what lag.",

            "An Earliest begin date is holding it. That is a floor and only "
            "ever pushes work later.",

            "It follows a calendar of its own. Check the Working calendar "
            "field in the editor - a weekend-only task cannot start on a "
            "Tuesday.",

            "Nothing silently changes a task's duration. Calendar changes "
            "hold the effort and move the finish, which is why a task can "
            "end later without holding any more work.",
        ],
    ),
    (
        "Where the log is",
        [
            "The Log button on the menu row opens what the application has "
            "been doing - imports, exports, calendar changes and anything "
            "that failed.",

            "It is also written to a file per platform: %LOCALAPPDATA% on "
            "Windows, ~/Library/Logs on macOS, and ~/.local/state (or "
            "$XDG_STATE_HOME) elsewhere, each under PySimplePMT.",

            "If something did not work and the reason is not on screen, the "
            "log is where it will be.",
        ],
    ),
)


class UserGuideWindow(ReferenceWindow):
    """
    The full guide, opened by the ? on the icon bar or View > Help.

    Larger than the two short references and searchable, which is the whole
    difference: they explain the form in front of the reader, and this
    answers a question they have arrived with.
    """

    TITLE = "Help"
    GEOMETRY = "820x720"
    MINSIZE = (560, 400)
    SECTIONS = GUIDE_SECTIONS
    SEARCHABLE = True

    #: Its own, so the guide and the two short references can all be open at
    #: once - see ReferenceWindow._open_window.
    _open_window = None


def show_user_guide(master=None):
    """
    Open the guide, or raise the copy already open.

    RETURNS:
    --------
    Optional[UserGuideWindow]
        The window, or None when it could not be built. A guide that fails to
        open should not take the button that opened it down with it.
    """
    return UserGuideWindow.show(master)

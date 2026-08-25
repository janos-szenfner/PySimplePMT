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

            "The list is grouped by region - Africa & Middle East, America, "
            "Asia Pacific, Europe - and alphabetical within each, so a "
            "country is found by knowing roughly where it is rather than by "
            "scrolling 250 names. A search that empties a region hides its "
            "heading with it. A country that straddles two continents is "
            "listed where somebody would look for it: Turkey, Russia, "
            "Armenia, Azerbaijan, Georgia and Cyprus are all under Europe.",

            "When nothing is selected the line under the search box says so "
            "in bold - it means the plan is working weekends off and no "
            "public holidays at all, which is worth noticing before you "
            "wonder why a date did not move.",

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

            "The dates run across the top as a calendar strip - a month "
            "band, and a cell per day beneath it carrying the day number. "
            "Too long a plan for that and it falls back to one cell per "
            "week, then to the month band alone. Days nobody works are "
            "shaded down the chart and today's column is tinted.",
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
        "Saying where the work has got to",
        [
            "The five buttons on the icon bar - 0%, 25%, 50%, 75%, 100% - "
            "set the completion of every selected row in one press. Status "
            "reporting is done to a list rather than to a row, so they take "
            "a whole selection at once, and the whole press is one step in "
            "the undo history.",

            "Mark on Track works the percentage out from the dates instead: "
            "work whose finish has gone by is set to 100%, work that has "
            "not started stays at 0%, and work in the middle is set to the "
            "share of its working days that have elapsed. A five-day task "
            "starting on a Friday is a fifth done by Sunday, not two "
            "fifths - the weekend is not worked, so it does not count.",

            "It measures against today. The arrow beside the button chooses "
            "what it applies to: the selected tasks, or the entire project. "
            "Entire Project needs nothing selected, which is why that arrow "
            "stays available when the rest of the group is greyed out.",

            "Mark on Track is a statement about the schedule rather than "
            "about the work. It fills in the rows nobody has had to think "
            "about, and the ones that are genuinely ahead or behind are "
            "still typed in.",

            "Pressing a percentage on a phase marks the work underneath it. "
            "A phase's own completion is rolled up from its children, so a "
            "number written straight onto it would be replaced the next "
            "time the plan is scheduled.",
        ],
    ),
    (
        "Marking rows up",
        [
            "The task list is where the work happens, and a plan of any size "
            "is scanned rather than read. The rows worth finding again - the "
            "payment milestones, the phase gates, the things that are "
            "finished - can be given a colour, a fill and an emphasis of "
            "their own so they are findable at a glance.",

            "Select one or more rows and use the formatting group on the "
            "icon bar: B, I and U for bold, italic and underline; the A for "
            "the text colour; the highlighter for the background fill. The "
            "bar under the A and the highlighter shows the colour each would "
            "apply next.",

            "Ctrl+B, Ctrl+I and Ctrl+U do the same from the keyboard, "
            "wherever the focus is in the window.",

            "The presets apply a whole look in one press: Financial "
            "Milestone is a yellow fill with bold black text, Deliverable "
            "Complete is green text at normal weight, Phase Gate / Approval "
            "is red bold italic, and Summary Phase is bold on a light slate "
            "fill.",

            "The X at the end of the group clears the formatting off the "
            "selected rows in one press, back to how the grid draws "
            "everything else.",

            "With several rows selected, a toggle shows as on only when "
            "every one of them has it, and a colour only when they all "
            "carry the same one - so pressing it means make them all this, "
            "which is what you meant by pressing it.",

            "Nothing is selected means nothing to format, so the whole "
            "group is greyed out until you pick a row.",

            "Formatting is part of the plan: it is saved with the file, it "
            "can be undone, and marking forty rows and pressing undo once "
            "puts all forty back.",
        ],
    ),
    (
        "Reading the outline",
        [
            "A row that has work under it is drawn in bold and carries the "
            "expander that folds its branch away. The work under it is "
            "indented one level per step down the plan.",

            "The Outline Level column says the same thing as a number: the "
            "top of the plan is 1, a row under it is 2, and so on. It is "
            "the same number Microsoft Project shows in its own Outline "
            "Level column.",

            "Indent moves a row under the row above it and Outdent brings "
            "it back out, and both move whole selections at once. A row "
            "that is already the first thing under its parent cannot be "
            "indented further - there is nothing above it at its own level "
            "to go under.",

            "Selecting a row and formatting it, indenting it or outdenting "
            "it leaves it selected, so a run of changes needs one click "
            "rather than one click each.",

            "That is true of any row with children, whatever the Type "
            "column says about it - a Task with sub-tasks is a summary of "
            "them. The hierarchy reads the same whether that column is on "
            "screen or scrolled out of sight, which is the point: scanning "
            "a list is exactly the activity that skips columns.",

            "A Phase or a Deliverable reads as a bracket even before "
            "anything has been put in it.",

            "A summary row can be told not to be bold, like any other row, "
            "and clearing its formatting brings the bold back - bold is "
            "what a summary is by default, not something applied to it.",
        ],
    ),
    (
        "The icon bar",
        [
            "The window opens filling whatever screen you are on, so the "
            "task list and the chart get whatever room the desktop allows.",

            "Every button says what it is if you rest the pointer on it, "
            "which is the fastest way to learn the row.",

            "Save and Save As come first, then the three that act on "
            "whichever task is selected in the list: edit it, indent it to "
            "sit under the row above, outdent it to sit beside its parent. "
            "Indent and outdent take several selected rows at once.",

            "Then the formatting group, set apart by a divider on each "
            "side because it changes how the plan is drawn rather than what "
            "it says - see Marking rows up above.",

            "The pencil edits the selected task. Renaming the plan itself is "
            "Actions > Project Title.",

            "Creating work items is on Actions > Create, and opening or "
            "starting a plan is on the Project menu.",

            "Then the critical path analysis, set apart on both sides "
            "because it neither edits a row nor moves one about, and then "
            "cut, copy, paste, delete, undo and redo.",
        ],
    ),
    (
        "Files: saving and opening",
        [
            "Project > Save and Project > Load use this application's own "
            "JSON format, which carries everything: the tasks, the links, "
            "the calendars, the overrides and the per-task calendar "
            "assignments.",

            "Save writes back to the file the plan came from and only asks "
            "where to put it the first time. Save As always asks, and the "
            "plan follows the new file from then on. A new plan has no file "
            "behind it, so Save asks again rather than writing over the one "
            "the last plan came from.",

            "A plan saved by an older version opens in a newer one. Anything "
            "the older version did not have is simply absent rather than "
            "wrong - a file written before named calendars existed opens "
            "with none, and every task in it follows the project's own.",
        ],
    ),
    (
        "Files: importing",
        [
            "File > Import reads four formats, none of which needs "
            "anything installed.",

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

            "MS Project - MSPDI .xml files, which is what Project writes "
            "from File > Save As > XML. The whole plan comes across: the "
            "outline, the dates, the links with their types and lags, "
            "progress, notes, priorities, the working calendar and the "
            "per-task calendars. Nothing needs installing.",

            "A binary .mpp cannot be read by anything except Project "
            "itself, so choosing one says so and names the one step that "
            "fixes it - open it in Project, File > Save As, pick XML "
            "Format, and import that. Nothing is guessed at from the "
            "binary: a plan that half-opened on invented dates would be "
            "worse than one that did not open.",
        ],
    ),
    (
        "Files: exporting",
        [
            "File > Export writes GAN, MS Project, Mermaid, HTML, SVG, PNG, "
            "PDF and XLSX.",

            "GAN - a GanttProject file. GanttProject stores a start and a "
            "duration rather than an end date and works the finish out from "
            "the calendar in the file, so the calendar goes with the plan "
            "and the durations are counted against it. The dates it shows "
            "are the dates shown here. The format holds one calendar, so a "
            "task following a named calendar of its own keeps its dates and "
            "loses the number of days it was given.",

            "MS Project - an .xml file in Microsoft's MSPDI interchange "
            "format, which Project opens with File > Open. It is not .mpp: "
            "nothing outside Project writes that format. Each piece of work "
            "carries a Start No Earlier Than constraint on the date the plan "
            "says, so opening the file does not re-solve the schedule - the "
            "links still push a task out when its predecessor slips, but "
            "nothing is pulled earlier than it was planned. Summary rows "
            "carry no constraint, since Project computes those from what is "
            "under them. Per-task calendars survive, which is the one thing "
            "this format holds and the GanttProject one does not.",

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

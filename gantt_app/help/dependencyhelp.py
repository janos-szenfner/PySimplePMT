"""
The reference window behind the Dependency tab's Help button.

WHY THIS MODULE EXISTS:
======================
The Dependency tab used to carry a block of explanatory text under its grid.
It could only afford a couple of lines per setting, it took room the grid
wanted, and it still left no space to say what lead time is or when to reach
for Finish - Finish. The full explanation lives here instead, and the tab
holds nothing but its controls.

DEVELOPMENT NOTES:
------------------
The text is written here rather than fetched, so the window works with no
network and nothing to download - the same rule the rest of the application
follows. It describes the standard scheduling concepts in this application's
own terms, using the names its own controls use.

Content is a plain data structure rather than markup so it stays readable in
the source and can be re-presented elsewhere - a printed sheet, a web page -
without unpicking formatting.
"""

from gantt_app.help.reference import ReferenceWindow


#: The reference text, as (heading, [paragraph, ...]).
#:
#: Written for this application: the names match the controls on the
#: Dependency tab, and the worked examples use its inclusive end dates.
HELP_SECTIONS = (
    (
        "What a dependency is",
        [
            "A dependency links two tasks so that one has to wait for the "
            "other. The task being waited on is the predecessor; the task "
            "doing the waiting is the successor.",

            "Every link you add on the Dependency tab is stored on the "
            "successor - the task you are editing - and names the "
            "predecessor it depends on. In the chart the link is drawn as an "
            "arrow running from the predecessor to the successor.",

            "Linking tasks rather than typing dates is what lets the plan "
            "hold together: move a task and everything waiting on it moves "
            "with it, so the schedule stays consistent instead of quietly "
            "going wrong.",
        ],
    ),
    (
        "The four types",
        [
            "Which two ends of the tasks a link ties together decides its "
            "type. Two of them decide when the successor may start, and two "
            "decide when it may finish.",
        ],
    ),
    (
        "Finish - Start (FS)",
        [
            "The successor starts after the predecessor finishes. This is "
            "the ordinary case and the default: one thing has to be done "
            "before the next can begin.",

            "Install the software, then train the staff on it. The training "
            "cannot start while the install is still running.",

            "End dates here cover the whole of their day, so a predecessor "
            "ending on the 5th lets its successor start on the 6th.",
        ],
    ),
    (
        "Start - Start (SS)",
        [
            "The successor starts once the predecessor has started. The two "
            "run alongside each other; the link only says the successor "
            "cannot be the one to go first.",

            "Turn the monitoring on, then begin the load test. The test can "
            "run at the same time as the monitoring, but starting it first "
            "would mean collecting nothing.",
        ],
    ),
    (
        "Finish - Finish (FF)",
        [
            "The successor finishes after the predecessor finishes. Again "
            "the two overlap, but this time it is the ends that are tied: "
            "the successor cannot be signed off first.",

            "Wiring up the interfaces and finalising the configuration go on "
            "together, but the configuration cannot be called finished until "
            "the wiring is.",
        ],
    ),
    (
        "Start - Finish (SF)",
        [
            "The successor finishes once the predecessor has started. This "
            "is the rarest of the four and usually describes a handover: "
            "something keeps running until its replacement is up.",

            "The old system stays live until the new one starts. Starting "
            "the new system is what allows the old one to be shut down.",
        ],
    ),
    (
        "Lag and lead",
        [
            "Lag is a wait built into the link, in working days. A Finish - "
            "Start link with a lag of 3 means the successor starts three "
            "working days after the predecessor finishes rather than the "
            "next one - curing time, a delivery, an approval that takes a "
            "week.",

            "Working days, so a wait means what it says wherever it falls. "
            "Counted in calendar days a lag of one or two over a weekend "
            "bought nothing: the date landed on the Saturday or the Sunday, "
            "and the task was pushed to the Monday it would have had anyway.",

            "A negative lag is lead time. It lets the successor begin before "
            "the predecessor is done, so the two overlap by that much. Lead "
            "is how a schedule is compressed without pretending the work "
            "takes less time: drafting can start on the last few days of "
            "research rather than waiting for all of it.",

            "Lag applies to whichever end the link type constrains, so a lag "
            "on a Finish - Finish link moves the successor's finish.",

            "The working days counted are the project's own, even where "
            "either task follows a calendar of its own. A lag is a number "
            "typed onto a link and it has to mean one thing: counted on the "
            "successor's week, the same lag of 2 was two days for an "
            "ordinary task and eight for one on a weekend-only shift. The "
            "successor's calendar still decides where it may start once the "
            "wait is over.",
        ],
    ),
    (
        "Link hardness",
        [
            "Hardness decides how strictly the date the link produces is "
            "applied. It is this application's own setting, and it matches "
            "what GanttProject files record, so a plan imported from there "
            "keeps its behaviour.",

            "Hard pins the date. Choosing the predecessor moves the "
            "successor onto the exact date the link gives.",

            "Rubber treats the date as a floor. The successor cannot fall "
            "earlier than the link allows, but it may sit later - which is "
            "what you want when a gap in the plan is deliberate rather than "
            "an accident.",

            "A task with both kinds of link has to satisfy both. A hard link "
            "pins the date, but not to somewhere a rubber link on another "
            "predecessor forbids: the later of the two applies.",
        ],
    ),
    (
        "How the plan reschedules itself",
        [
            "Moving a task moves whatever depends on it. The schedule "
            "settles after every change: links are applied from the "
            "predecessors forward, so a whole chain shifts in one go.",

            "That pass only ever moves a task later. It repairs a successor "
            "that would start too early and it follows a predecessor that "
            "moves out, but it leaves gaps alone - a plan imported from "
            "GanttProject has its dates worked out around weekends and "
            "holidays, and closing those gaps would put it on dates the "
            "original never showed.",

            "Choosing a predecessor on the Dependency tab is the exception: "
            "that places the task on the link's date straight away, which is "
            "what fills the start date in for you.",
        ],
    ),
    (
        "Tasks, sub-tasks and milestones",
        [
            "A task with sub-tasks brackets them rather than holding work of "
            "its own. Its dates come from its children - the earliest start "
            "and the latest finish - and its progress is their average, "
            "weighted by how long each one lasts. The chart draws it as a "
            "bracket instead of a solid bar.",

            "A milestone marks a moment and takes no time, so it has no end "
            "date and no sub-tasks. Because it occupies no day, a task "
            "following a milestone on the 15th starts on the 15th, not the "
            "16th.",

            "A dependency on a task that has sub-tasks means a dependency on "
            "the work inside it.",
        ],
    ),
    (
        "Avoiding trouble",
        [
            "Two tasks cannot wait on each other. A loop has no schedule "
            "that satisfies it, so the plan stops settling rather than "
            "chasing itself; if dates stop responding to a change, look for "
            "a cycle in the links.",

            "A task cannot depend on itself or on its own sub-tasks, and the "
            "Dependency tab leaves those out of the list of predecessors.",

            "Prefer a link to a fixed date wherever the order is what "
            "actually matters. A typed date is right until something moves; "
            "a link stays right.",
        ],
    ),
)


class DependencyHelpWindow(ReferenceWindow):
    """
    A scrollable reference on dependency links.

    DEVELOPMENT NOTES:
    ------------------
    Everything but the words is in ReferenceWindow, which the editor's Help
    button shares. Only one of these is kept open at a time - see `show` -
    because the Help button sits next to controls people click repeatedly and
    stacking up identical windows helps nobody.
    """

    TITLE = "Dependencies - Help"
    GEOMETRY = "720x640"
    SECTIONS = HELP_SECTIONS

    #: This window's own; the editor's reference keeps a separate one.
    _open_window = None

"""
Finding a row by anything written on it.

WHY THIS MODULE EXISTS:
======================
A plan of any size is a list nobody can scan. The row somebody is looking for
is known by whatever they happen to remember about it - a word from its name,
the ticket number somebody typed into its notes, the date it starts, the
person's initials in a detail line - and until now the only way to find it was
to read the list.

So the box searches everything a work item carries: its name and id, its type,
its notes, both its dates, its duration and progress, its priority, its
status, what it depends on, and which calendar it follows. One box, no field
to choose first, because a reader who knew which field it was in would not
need to search.

DEVELOPMENT NOTES:
------------------
The matching is pure and lives at the top of this module: it takes a task and
a project and returns a string or a bool, touches no widget, and is tested
without a display. The widget below is a box, a count and a Clear button, and
hands what was typed to a callback. Which rows that then hides belongs to the
task list, which owns the tree.

Matching keeps a row's **ancestors** on screen. That is not what the type
filter this shares a toolbar with would do - "show only Milestones" has to
stop showing Phases, or it has not done what was asked - but a search is a
different question. "Where is the mockup task" is answered better by showing
where it sits than by a row floating at the top level with its context
removed.
"""

import tkinter as tk
from typing import Callable, List, Optional, Set

import customtkinter as ctk

from gantt_app import theme
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

#: How long typing has to stop before the list is rebuilt, in milliseconds.
#:
#: Every keystroke would otherwise rebuild the whole tree and, through it,
#: redraw the chart. A tenth of a second is below what anybody notices and
#: turns "milestone" from nine rebuilds into one.
SETTLE_MS = 120


def task_haystack(task, project=None) -> str:
    """
    Everything written on one work item, as one lower-case string.

    PARAMETERS:
    -----------
    task : Task
        The row to describe.
    project : Optional[Project]
        The plan it belongs to. Given one, the name of the calendar the task
        follows is included - the task stores only the id, and the name is
        what a reader would search for.

    RETURNS:
    --------
    str
        The searchable text, lower case, fields separated by spaces.

    DEVELOPMENT NOTES:
    ------------------
    Dates go in as YYYY-MM-DD, which is how they are written everywhere else
    in the application, so "2026-09" finds a September and "2026-09-14" finds
    the day. The duration and the progress go in as bare numbers, so "14"
    finds a fortnight's work as well as the fourteenth.

    Everything is included rather than a chosen few. A field left out is a
    field somebody searches for once and concludes the search is broken.
    """
    # The number shown beside the row, not Task.id. The identity is a key
    # the reader never sees - see Project.display_ids - so searching for it
    # would match rows by a number that is nowhere on screen, and searching
    # for the number that *is* on screen would find the wrong row.
    numbers = project.display_ids() if project is not None else {}
    if task.id in numbers:
        parts_head = [str(numbers[task.id]),
                      str(numbers[task.id]).zfill(project.ID_WIDTH)]
    else:
        parts_head = []

    parts: List[str] = parts_head + [
        str(task.name or ''),
        str(task.task_type or ''),
        str(task.details or ''),
        str(task.priority or ''),
        str(task.status or ''),
        str(task.shape or ''),
    ]

    for moment in (task.start_date, task.end_date, task.earliest_begin):
        if moment is not None:
            parts.append(moment.strftime('%Y-%m-%d'))

    if task.duration is not None:
        parts.append(str(task.duration))
    parts.append(str(task.progress))

    if task.is_milestone or task.task_type == 'Milestone':
        parts.append('milestone')

    # The link's own fields, and the id it points at - but deliberately not
    # the predecessor's *name*. Including it meant searching a task by name
    # also returned everything depending on that task, so the commonest
    # search of all came back with rows that only mentioned the thing being
    # looked for. The id still finds both, which is the precise way to ask.
    for link in task.dependencies:
        # By the number it is shown as, for the same reason as above
        if link.task_id in numbers:
            parts.append(str(numbers[link.task_id]))
            parts.append(str(numbers[link.task_id]).zfill(project.ID_WIDTH))
        parts.append(str(link.dep_type or ''))
        parts.append(str(link.hardness or ''))
        if link.lag:
            parts.append(str(link.lag))

    if project is not None and getattr(task, 'calendar_id', None):
        named = project.calendars.get(task.calendar_id)
        parts.append(task.calendar_id)
        if named is not None:
            parts.append(named.name)

    return ' '.join(part for part in parts if part).lower()


def task_matches(task, needle: str, project=None) -> bool:
    """
    Whether a work item carries the text somebody typed.

    Matched without regard to case and taken literally, so "2026-09-14" and
    "24/7" find themselves rather than being read as patterns. An empty or
    blank search matches everything, which is what makes clearing the box
    the same as never having typed in it.
    """
    needle = (needle or '').strip().lower()
    if not needle:
        return True
    return needle in task_haystack(task, project)


def visible_task_ids(project, needle: str) -> Optional[Set[str]]:
    """
    Which rows a search should leave on screen.

    RETURNS:
    --------
    Optional[Set[str]]
        The ids to show, or None when nothing was searched for - which the
        task list reads as "no filter" rather than as "show nothing", so an
        empty box costs it no work at all.

    DEVELOPMENT NOTES:
    ------------------
    A match brings its ancestors with it. Without them a matching sub-task
    appears at the top level with no sign of what it belongs to, and the
    indentation - which is the only thing saying how the plan is put
    together - would be showing a structure that is not there.

    Their children are *not* brought along. A Phase whose name matches shows
    as itself; showing everything inside it would answer a question nobody
    asked, and on a big plan one broad word would put the whole list back on
    screen.
    """
    needle = (needle or '').strip()
    if not needle:
        return None

    by_id = {task.id: task for task in project.tasks}
    visible: Set[str] = set()

    for task in project.tasks:
        if not task_matches(task, needle, project):
            continue

        visible.add(task.id)

        # Walk up, guarding against a parent chain that loops - a damaged
        # file can carry one, and this would otherwise never return.
        seen = {task.id}
        parent_id = task.parent_task_id
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            visible.add(parent_id)
            parent = by_id.get(parent_id)
            if parent is None:
                break
            parent_id = parent.parent_task_id

    return visible


def matching_task_ids(project, needle: str) -> Set[str]:
    """
    The rows that match in their own right, without their ancestors.

    What the count reports, and what the task list shades: an ancestor is on
    screen to say where a match sits, not because it is one.
    """
    needle = (needle or '').strip()
    if not needle:
        return set()
    return {task.id for task in project.tasks
            if task_matches(task, needle, project)}


class TaskSearchBox(ctk.CTkFrame):
    """
    The box on the icon bar, and the count beside it.

    PARAMETERS:
    -----------
    master : widget
        The row to sit in.
    on_search : Callable[[str], None]
        Called with what has been typed, once typing has settled. The caller
        decides what to hide; this only says what was asked for.
    width : int
        How wide the entry should be.

    DEVELOPMENT NOTES:
    ------------------
    Debounced rather than firing per keystroke - see SETTLE_MS. Rebuilding
    the tree redraws the chart with it, and doing that nine times while
    somebody types "milestone" is nine full renders nobody sees.
    """

    def __init__(self, master, on_search: Callable[[str], None],
                 width: int = 190, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)

        self.on_search = on_search
        self._settle_job = None

        self.search_var = ctk.StringVar()
        self.search_var.trace_add('write', self._typed)

        self.entry = ctk.CTkEntry(
            self, textvariable=self.search_var, width=width, height=28,
            placeholder_text="Search tasks, notes, dates...")
        self.entry.pack(side=tk.LEFT)
        # Enter searches at once rather than waiting out the delay, and
        # Escape clears - which is what every other search box does.
        self.entry.bind('<Return>', lambda _event: self._fire_now())
        self.entry.bind('<Escape>', lambda _event: self.clear())

        self.count_label = ctk.CTkLabel(self, text="", width=74, anchor=tk.W,
                                        text_color=theme.MUTED_TEXT)
        self.count_label.pack(side=tk.LEFT, padx=(6, 0))

        self.clear_button = secondary_clear_button(self, self.clear)
        # Packed by report(), so an empty box carries no chrome at all.

    @property
    def needle(self) -> str:
        """What is currently typed, stripped."""
        return self.search_var.get().strip()

    def _typed(self, *_args):
        """Restart the settle timer; see SETTLE_MS."""
        self._cancel_settle()
        try:
            self._settle_job = self.after(SETTLE_MS, self._fire_now)
        except tk.TclError:
            self._fire_now()

    def destroy(self):
        """
        Cancel the settle timer before the box goes.

        A pending timer would otherwise fire _fire_now on a dead widget. The
        box lives as long as the toolbar, so this is tidiness rather than a
        leak, but the timer should not outlast what scheduled it. Done in a
        destroy() override rather than off a <Destroy> binding because a
        CustomTkinter widget's own <Destroy> does not reach a self.bind
        handler - only its internal canvas child's does.
        """
        self._cancel_settle()
        super().destroy()

    def _cancel_settle(self):
        """Drop a pending search, if there is one."""
        if self._settle_job is None:
            return
        try:
            self.after_cancel(self._settle_job)
        except (tk.TclError, ValueError):
            pass
        self._settle_job = None

    def _fire_now(self):
        """Hand what was typed to the caller."""
        self._cancel_settle()
        if self.on_search is None:
            return
        try:
            self.on_search(self.needle)
        except Exception:
            logger.exception("The task search failed")

    def clear(self):
        """Empty the box, which puts every row back."""
        self._cancel_settle()
        self.search_var.set('')
        self._fire_now()

    def report(self, shown: int, total: int):
        """
        Say how much of the plan is on screen, and offer a way back.

        DEVELOPMENT NOTES:
        ------------------
        The count is the safeguard, not decoration. A filtered list looks
        exactly like a short plan, and somebody who has forgotten the box has
        text in it will read one as the other. The Clear button appears with
        it, so the way out is beside the thing that needs explaining.
        """
        try:
            if not self.count_label.winfo_exists():
                return
        except tk.TclError:
            return

        if not self.needle:
            self.count_label.configure(text="")
            self.clear_button.pack_forget()
            return

        self.count_label.configure(text=f"{shown} of {total}")
        if not self.clear_button.winfo_manager():
            self.clear_button.pack(side=tk.LEFT, padx=(6, 0))


def secondary_clear_button(master, command):
    """
    The Clear button, in the toolbar's quieter style.

    Built here rather than inline so the import of buttonstyle stays in one
    place; see gantt_app.views.buttonstyle.
    """
    from gantt_app.views.buttonstyle import secondary_button

    return secondary_button(master, "Clear", command, width=54, height=28)

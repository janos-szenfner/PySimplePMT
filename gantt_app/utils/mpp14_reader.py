"""
Microsoft Project import: reading a binary .mpp back into a plan.

WHY THIS MODULE EXISTS:
======================
For a long time a binary .mpp was the file this application could only
identify: an OLE2 compound document of undocumented streams that nothing
outside Project was believed to read. That is no longer true. pymppwriter -
a small, pure-Python package - reads the MPP14 container the way MPXJ does:
every field offset comes from the field maps the file itself carries, so a
file written by any Project from 2010 on parses rather than being declined.

This module is the seam between that package and this application. It turns
pymppwriter's generic read into the same plan the MSPDI importer produces -
the one Project itself writes with File > Save As > XML - so an .mpp and the
XML saved from it land as the same tasks either way.

WHAT COMES BACK:
================
What the XML importer maps: the hierarchy, the dates, the durations, the
links with their types and lags, progress, priorities, notes and the SNET
constraints. Resources, assignments, baselines and calendars exist in the
file and pymppwriter reads them, but the MSPDI path does not map them into
the plan either, so they are left alone here as well until both paths grow
them together.

WHAT IS NOT READ:
=================
MPP14 is the format of Project 2010 and everything after. Anything older -
MPP9 and MPP12 era files - fails cleanly: pymppwriter raises and this module
returns None, which is what sends the user to the Save-As-XML guidance, the
same answer they always got. Password-protected and corrupt files end up
there too, because a plan that half-parses into plausible dates is worse
than one that refuses to open.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from gantt_app.core.models import Project, Task, child_type_for
from gantt_app.core.workdaycalendar import WorkingCalendar
from gantt_app.utils.log import get_logger
from gantt_app.utils.msproject_importer import (
    DEFAULT_COLOR, MILESTONE_COLOR, _inclusive_end, _parse_priority,
    _task_type,
)

logger = get_logger(__name__)

#: The dependency type letters pymppwriter reports are already this
#: application's own, so the relation needs no translating, only a guard.
DEPENDENCY_TYPES = {'FF', 'FS', 'SF', 'SS'}


def _build_tasks(source) -> List[Task]:
    """
    Every task row the reader surfaced, in file order.

    DEVELOPMENT NOTES:
    ------------------
    pymppwriter skips the project summary row (uid 0) and stub records, so
    every task here is real work. Hierarchy comes off the file's own
    parent_uid, walked up to the nearest row that was imported: generated
    plans jump outline levels and store children rows away from the summary
    they belong to, which the outline-level stack reads as parent-child
    edges the file never made - that mis-parenting is what once nested a
    task under a same-named row in another phase and turned its ordinary
    link into one against its own parent. The stack stays as the fallback
    for a row whose parent link is missing, and for files whose writer left
    the field empty.

    A task is a summary row when some imported row's parent chain lands on
    it. That is how the file itself records the fact; the outline stack
    alone cannot see a phase's last task until the phase ends.
    """
    # The file's own parent links, kept for every row - including the ones
    # that are skipped - so a child parked under a start-less placeholder
    # can be walked up to the nearest ancestor that was imported instead of
    # falling on whatever row the outline stack happens to hold. The walk
    # is guarded: a link chain that loops back on itself reports no parent.
    file_parents = {t.uid: t.parent_uid for t in source.tasks}
    started_uids = {t.uid for t in source.tasks if t.start is not None}

    def resolved_parent(uid) -> Optional[int]:
        seen = {uid}
        cur = file_parents.get(uid)
        while cur is not None:
            if cur in seen:
                return None
            seen.add(cur)
            if cur in started_uids:
                return cur
            cur = file_parents.get(cur)
        return cur

    # A task is a summary row when some imported row's parent chain lands
    # on it; children that were skipped do not make one.
    parent_uids = {resolved_parent(t.uid) for t in source.tasks
                   if t.uid in started_uids}

    tasks: List[Task] = []
    by_uid: Dict[int, Task] = {}
    stack: List[Task] = []
    stack_parents: List[Optional[Task]] = []

    for row in source.tasks:
        if row.start is None:
            logger.warning("Task %r has no start date; it is not imported",
                           row.name)
            continue

        level = max(int(row.outline_level), 1)
        is_summary = row.uid in parent_uids
        is_milestone = row.duration_days == 0 and not is_summary

        start = datetime(row.start.year, row.start.month, row.start.day)
        end = start if is_milestone else _inclusive_end(start, row.finish)
        if end is None and not is_milestone and row.duration_days:
            end = WorkingCalendar().add_working_days(
                start, max(int(round(row.duration_days)) - 1, 0))

        del stack[level - 1:]
        stack_parent = stack[-1] if stack else None

        task = Task(
            id=str(row.uid),
            name=(row.name or '').strip() or 'Unnamed Task',
            start_date=start,
            end_date=end,
            duration=(int(round(row.duration_days))
                      if row.duration_days else None),
            progress=max(0, min(100, int(row.percent_complete))),
            dependencies=[],
            color=MILESTONE_COLOR if is_milestone else DEFAULT_COLOR,
            task_type=_task_type(is_milestone, is_summary, level),
            is_milestone=is_milestone,
            parent_task_id=None,
            priority=_parse_priority(str(row.priority)),
            details=row.notes or '',
            manually_scheduled=row.manual,
            # Imported rows were drawn where they came from (issue #72)
            show_in_timeline=True,
        )

        # The only constraint the model carries, and only when it says
        # something the dates don't already - see msproject_importer (#32).
        if (row.constraint == 'SNET' and row.constraint_date is not None
                and row.constraint_date.date() != start.date()):
            task.constraint_type = 'SNET'
            task.constraint_date = datetime(
                row.constraint_date.year, row.constraint_date.month,
                row.constraint_date.day)

        by_uid[row.uid] = task
        tasks.append(task)
        stack.append(task)
        stack_parents.append(stack_parent)

    # Second pass: wire the parents the file names, falling back to the
    # outline stack only where the file is silent. A row cannot parent
    # itself, and a parent that was not imported resolves to the nearest
    # ancestor that was - or to nothing, which the stack then answers.
    for task, stack_parent in zip(tasks, stack_parents):
        parent = by_uid.get(resolved_parent(int(task.id)))
        if parent is None or parent is task:
            parent = stack_parent
        task.parent_task_id = parent.id if parent else None
        task.task_type = child_type_for(parent, task)

    # The records come back in stored order, not outline order - this file
    # parks children rows away from the summary they belong to. The grid
    # and the exports both read the list straight, so walk the tree the
    # file described and lay the rows down the way the outline reads.
    children: Dict[Optional[str], List[Task]] = {}
    for task in tasks:
        children.setdefault(task.parent_task_id, []).append(task)
    ordered: List[Task] = []
    seen_ids = set()

    def visit(task):
        if task.id in seen_ids:
            return
        seen_ids.add(task.id)
        ordered.append(task)
        for child in children.get(task.id, []):
            visit(child)

    for task in tasks:
        if task.parent_task_id is None:
            visit(task)
    for task in tasks:
        visit(task)
    tasks[:] = ordered

    for relation in source.relations:
        successor = by_uid.get(relation.succ_uid)
        predecessor = by_uid.get(relation.pred_uid)
        if successor is None or predecessor is None:
            logger.warning("Link between UIDs %s and %s names a task that is "
                           "not in the file; the link is dropped",
                           relation.pred_uid, relation.succ_uid)
            continue
        dep_type = relation.type if relation.type in DEPENDENCY_TYPES else 'FS'
        successor.add_dependency(predecessor.id, dep_type=dep_type,
                                 hardness='Hard',
                                 lag=int(round(relation.lag_days)))

    return tasks


def parse_mpp14(source, filepath: str) -> Project:
    """
    Build a project from what pymppwriter read.

    PARAMETERS:
    -----------
    source : pymppwriter.Project
        The generic project the binary reader surfaced.
    filepath : str
        Where it came from - a title is taken from the file name when the
        plan itself does not carry one.

    RETURNS:
    --------
    Project
        The plan the file describes.
    """
    tasks = _build_tasks(source)
    name = source.title or Path(filepath).stem

    project = Project(name=name, name_was_set=True, tasks=tasks,
                      calendar=WorkingCalendar())
    if source.start is not None:
        project.start_date = datetime(source.start.year, source.start.month,
                                      source.start.day)
    return project


def import_mpp14_file(filepath: str) -> Optional[Project]:
    """
    Import a binary Microsoft Project (.mpp) file.

    PARAMETERS:
    -----------
    filepath : str
        Path to the file.

    RETURNS:
    --------
    Optional[Project]
        The plan, or None when the file cannot be read - an older MPP
        version, a protected file, or bytes that are not a project at all.
        The caller answers None with the Save-As-XML guidance, which stays
        the way forward for every file this cannot open.

    EXAMPLE:
    --------
    >>> from gantt_app.utils.mpp14_reader import import_mpp14_file
    >>> project = import_mpp14_file("/path/to/plan.mpp")
    """
    try:
        from pymppwriter import MppReadError, read_project
    except ImportError:
        logger.error("pymppwriter is not installed; cannot read %s",
                     filepath)
        return None

    try:
        source = read_project(filepath)
    except (MppReadError, OSError) as exc:
        # OSError covers olefile's own NotOleFileError - a file that is
        # not the container it claimed to be. Both mean the file is not
        # readable, which is the user's problem to solve with Save As
        # XML, not this application's to log as an error.
        logger.warning("Could not read %s as an MPP14 project: %s",
                       filepath, exc)
        return None
    except Exception:
        logger.exception("Could not import the MS Project file %s",
                         filepath)
        return None

    project = parse_mpp14(source, filepath)
    logger.info("Imported %d task(s) from the binary MS Project file %s",
                len(project.tasks), filepath)
    return project

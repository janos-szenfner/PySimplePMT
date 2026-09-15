"""
The Resource Usage grid: the pool as a tree, with each entity's tasks
hanging under it.

WHY THIS MODULE EXISTS:
======================
The Resource Planning tab's second face, beside the allocation matrix the
ResourceBoard draws. Where the matrix answers "who is loaded when", this
grid answers "what does each resource own" - MS Project's Resource Usage
view, with the deliverables board's shape: a ttk.Treeview whose #0 column
carries the name beside the outline's indent, a read-only gutter pinned
to its left for the row number and the mark box, and editors reached by
double-click and right-click rather than typed into cells.

The sections are the pool's kinds, top to bottom: teams, generic
resources, named resources, materials, cost resources. A resource that
belongs to a team also shows under it, in italic - the team's row is a
lens onto its members, not a folder that would move them out of their own
section. Under every entity row hang the tasks its assignments name, as
read-only rows like the deliverables board's, so an assignment made here
reads the same as one made there.

DEVELOPMENT NOTES:
------------------
Pool changes - create, edit, delete, a membership change - go through
project_tracker.run_resource_as_command or record_resource_pool_change,
and deletes that also prune task assignments go through run_as_command,
whose snapshot covers both collections. Assignment changes go through
update_task/update_tasks, which already carry resource_assignments. A
press of Undo therefore puts back whatever the grid did - see
SnapshotCommand and ResourcePoolSnapshotCommand in utils/undoredo.

Row ids carry their kind as a prefix so a task row is never mistaken for
an entity: 'res:', 'team:', 'mat:', 'cost:' are canonical rows,
'alias:' a team's member lens, and 'task:<parent iid>:<task id>:<n>'
the n-th assignment of the parent entity on that task.
"""

import copy
import tkinter as tk
import tkinter.font as tkfont
from tkinter import simpledialog, ttk
from typing import Callable, Dict, List, Optional, Set

import customtkinter as ctk

from gantt_app.views import theme
from gantt_app.views import dialogs as messagebox
from gantt_app.views.modal import grab_when_visible
from gantt_app.core.models import Project, Task
from gantt_app.core.resource_model import (
    Resource, ResourceType, TeamPool, MaterialResource, CostResource,
    material_quantity)
from gantt_app.core import effort as eff
from gantt_app.views.statusline import entity_status_line, task_status_line
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: The mark box drawn in the gutter: not marked, marked.
MARK_NONE = '[ ]'
MARK_SET = '[x]'

#: The glyphs the Progress cell's bar is drawn from, six cells wide.
BAR_FILL = '▓'
BAR_EMPTY = '░'
BAR_CELLS = 6

#: The filter the type dropdown offers beyond the five real kinds.
FILTER_ALL = 'All'
TYPE_FILTERS = (FILTER_ALL, 'Team', 'Generic', 'Named', 'Material',
                'Cost')


class ResourceUsageGrid(ctk.CTkFrame):
    """
    The resource usage grid - the Resource Planning tab's grid view.

    PARAMETERS:
    -----------
    parent : widget
        The ResourceBoard frame this shares the tab with.
    project : Project
        The active project, whose pool and assignments the grid draws.
    on_status : Callable[[str], None], optional
        Where a line for the reader goes - the footer's status bar.
    on_project_changed : Callable[[], None], optional
        Fired after a change, so the rest of the window refreshes.
    project_tracker : optional
        The undo tracker; every mutation is run through it when given.
    """

    GRID_ROW_HEIGHT = 26

    #: The data columns, in display order. The name is the tree column
    #: (#0), which is what draws the indentation and the expander.
    COLUMNS = ('Type', 'Initials', 'Group', 'Detail', 'Tasks',
               'Committed', 'Progress')

    COLUMN_WIDTHS = {
        '#0': 300, 'Type': 80, 'Initials': 70, 'Group': 110,
        'Detail': 150, 'Tasks': 90, 'Committed': 110, 'Progress': 120,
    }

    def __init__(self, parent, project: Project,
                 on_status: Optional[Callable[[str], None]] = None,
                 on_project_changed: Optional[Callable[[], None]] = None,
                 project_tracker=None) -> None:
        super().__init__(parent)
        self.project = project
        self.on_status = on_status
        self.on_project_changed = on_project_changed
        self.project_tracker = project_tracker

        #: Rows ticked for a bulk action, by entity id. Kept across
        #: rebuilds, which is the point of marks over the cursor selection.
        self._marked: Set[str] = set()

        #: The column the grid was last sorted by, and which way.
        self._sort_column = None
        self._sort_reverse = False

        self._build_ui()
        self._apply_grid_style()
        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """The header strip, then the grid."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color='transparent')
        header.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 4))

        ctk.CTkLabel(
            header, text='Resource Usage',
            font=ctk.CTkFont(weight='bold', size=14),
        ).pack(side=tk.LEFT)

        self.search_entry = ctk.CTkEntry(
            header,
            placeholder_text='Filter by name, initials or group…',
            width=220)
        self.search_entry.pack(side=tk.LEFT, padx=(16, 6))
        self.search_entry.bind('<KeyRelease>',
                               lambda _e: self.refresh())

        self.type_filter = ctk.CTkOptionMenu(
            header, values=list(TYPE_FILTERS), width=110,
            command=lambda _v: self.refresh())
        self.type_filter.set(FILTER_ALL)
        self.type_filter.pack(side=tk.LEFT, padx=6)

        new_button = ctk.CTkButton(
            header, text='+ New ▾', width=100,
            command=lambda: self._open_new_menu(new_button))
        new_button.pack(side=tk.LEFT, padx=6)
        self._new_button = new_button

        # The grid: a fixed gutter carrying the row number and the mark
        # box, then the tree, then the scrollbars - the layout the task
        # list and the deliverables board already share, which is how the
        # number stays put while the columns scroll.
        grid_frame = ctk.CTkFrame(self)
        grid_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10,
                        pady=(0, 10))
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)

        self.id_tree = ttk.Treeview(
            grid_frame, columns=(), show='tree headings',
            selectmode='none', takefocus=0)
        self.id_tree.heading('#0', text='No', anchor=tk.W)
        self.id_tree.column('#0', width=72, minwidth=56, stretch=False,
                            anchor=tk.W)
        self.id_tree.bind('<Button-1>', self._on_gutter_click)
        for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.id_tree.bind(seq, self._gutter_wheel)

        self.tree = ttk.Treeview(
            grid_frame, columns=self.COLUMNS, show='tree headings')
        self.tree.heading('#0', text='Name', anchor=tk.W,
                          command=lambda: self._heading_clicked('#0'))
        for name in self.COLUMNS:
            self.tree.heading(name, text=name, anchor=tk.W,
                              command=lambda n=name:
                              self._heading_clicked(n))
            anchor = tk.CENTER if name in ('Type', 'Initials',
                                           'Progress') else tk.W
            self.tree.column(name, width=self.COLUMN_WIDTHS[name],
                             minwidth=50, stretch=False, anchor=anchor)
        self.tree.column('#0', width=self.COLUMN_WIDTHS['#0'],
                         minwidth=140, stretch=False)

        vsb = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL,
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL,
                            command=self.tree.xview)
        theme.style_scrollbar(vsb)
        theme.style_scrollbar(hsb)
        self._vertical_scrollbar = vsb
        self.tree.configure(yscrollcommand=self._rows_scrolled,
                            xscrollcommand=hsb.set)

        self.id_tree.grid(row=0, column=0, sticky=tk.NS)
        self.tree.grid(row=0, column=1, sticky=tk.NSEW)
        vsb.grid(row=0, column=2, sticky=tk.NS)
        hsb.grid(row=1, column=1, sticky=tk.EW)

        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<<TreeviewSelect>>',
                       lambda _e: self._push_selection_status(),
                       add='+')
        self.tree.bind('<<TreeviewOpen>>',
                       lambda _e: self.after_idle(self._refresh_gutter),
                       add='+')
        self.tree.bind('<<TreeviewClose>>',
                       lambda _e: self.after_idle(self._refresh_gutter),
                       add='+')
        self._bind_context_menu()

    def _apply_grid_style(self) -> None:
        """Colour the grid for the appearance now in force."""
        theme.style_treeview('ResourceUsage.Treeview',
                             row_height=self.GRID_ROW_HEIGHT)
        ttk.Style().configure('ResourceUsage.Treeview', indent=24)
        self.tree.configure(style='ResourceUsage.Treeview')
        self._apply_gutter_style()
        self._apply_row_tag_colours()

    def _apply_row_tag_colours(self) -> None:
        """
        Resolve the row appearances against the theme now in force.

        The band tags are the grid's own; 'alias' is the italic a team
        member's lens row wears, and 'parent' the bold a section parent
        could take - the same tag-names the task list and the
        deliverables board use, so a theme change re-colours them here.
        """
        self.tree.tag_configure(
            'evenrow', background=theme.now(theme.GRID_ROW_BG),
            foreground=theme.now(theme.GRID_TEXT))
        self.tree.tag_configure(
            'oddrow', background=theme.now(theme.GRID_ROW_ALT),
            foreground=theme.now(theme.GRID_TEXT))
        try:
            base = tkfont.nametofont('TkDefaultFont')
            family, size = base.cget('family'), base.cget('size')
            self.tree.tag_configure(
                'alias', font=(family, size, 'italic'))
            self.tree.tag_configure(
                'parent', font=(family, size, 'bold'))
        except tk.TclError:
            pass        # no display font to derive from; rows stay plain

    def _apply_gutter_style(self) -> None:
        """Grey the fixed gutter, the same shade the task list's wears."""
        theme.style_treeview('IdGutter.Treeview',
                             row_height=self.GRID_ROW_HEIGHT)
        style = ttk.Style()
        grey = theme.now(theme.FIELD_BG_DISABLED)
        muted = theme.now(theme.MUTED_TEXT)
        style.configure('IdGutter.Treeview', background=grey,
                        fieldbackground=grey, foreground=muted, indent=0)
        style.map('IdGutter.Treeview',
                  background=[('selected', grey)],
                  foreground=[('selected', muted)])
        self.id_tree.configure(style='IdGutter.Treeview')

    # ------------------------------------------------------------------
    # The view contract - what main.py asks of every pane
    # ------------------------------------------------------------------

    def on_shown(self) -> None:
        """Called when the tab brings the grid to the front."""
        self.refresh()

    def apply_theme(self) -> None:
        """Re-colour the grid for the appearance just switched to."""
        try:
            if not self.tree.winfo_exists():
                return
        except tk.TclError:
            return
        self._apply_grid_style()
        self._paint_rows()

    def refresh(self) -> None:
        """
        Rebuild every row from the project's pool and assignments.

        Rebuilding throws away the rows the reader had acted on, so the
        selection, the folds and the scroll position are carried across -
        the task list's update_task_list rule.
        """
        state = self._capture_view_state()

        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
        except tk.TclError:
            return

        # Marks pointing at entities that have gone are dropped, or a
        # mark would live on an id nothing can un-tick.
        self._marked = {i for i in self._marked
                        if self._entity_by_id(i) is not None}

        repo = self.project.resource_repository
        search = (self.search_entry.get() or '').strip().lower()
        type_filter = self.type_filter.get()

        def matches(entity) -> bool:
            if not search:
                return True
            haystack = ' '.join(
                str(getattr(entity, name, '') or '')
                for name in ('name', 'initials', 'group', 'role_type',
                             'material_label'))
            return search in haystack.lower()

        def section_wanted(kind: str) -> bool:
            return type_filter in (FILTER_ALL, kind)

        # The sections in the order the request asked for: teams, generic
        # resources, named resources, then materials and cost resources.
        sections = [
            ('Team', 'team',
             sorted(repo.teams.values(), key=lambda t: t.name.lower())
             if section_wanted('Team') else []),
            ('Generic', 'res',
             sorted((r for r in repo.resources.values()
                     if r.resource_type == ResourceType.GENERIC),
                    key=lambda r: r.name.lower())
             if section_wanted('Generic') else []),
            ('Named', 'res',
             sorted((r for r in repo.resources.values()
                     if r.resource_type == ResourceType.NAMED),
                    key=lambda r: r.name.lower())
             if section_wanted('Named') else []),
            ('Material', 'mat',
             sorted(repo.materials.values(), key=lambda m: m.name.lower())
             if section_wanted('Material') else []),
            ('Cost', 'cost',
             sorted(repo.costs.values(), key=lambda c: c.name.lower())
             if section_wanted('Cost') else []),
        ]

        for type_label, prefix, entities in sections:
            for entity in self._sorted_entities(entities):
                is_team = isinstance(entity, TeamPool)
                if is_team:
                    members = self._team_members(entity)
                    # A member matching the search keeps its team on
                    # screen, the way a matching child keeps its parent.
                    if search and not matches(entity) \
                            and not any(matches(m) for m in members):
                        continue
                elif not matches(entity):
                    continue

                item_id = self.tree.insert(
                    '', tk.END, iid=f'{prefix}:{entity.id}',
                    text=entity.name or '(unnamed)', open=True,
                    values=self._row_values(entity, type_label))

                if is_team:
                    for member in members:
                        if search and not matches(entity) \
                                and not matches(member):
                            continue
                        alias_id = self._alias_id(entity.id, member.id)
                        self.tree.insert(
                            item_id, tk.END, iid=alias_id, open=True,
                            text=member.name or '(unnamed)',
                            values=self._alias_row_values(member, entity))
                        self._insert_task_rows(alias_id, member.id)
                self._insert_task_rows(item_id, entity.id)

        self._paint_rows()
        self._restore_view_state(state)
        self._refresh_gutter()

    # ------------------------------------------------------------------
    # Row ids - what a tree item stands for
    # ------------------------------------------------------------------

    @staticmethod
    def _alias_id(team_id: str, resource_id: str) -> str:
        """The tree id a member's lens row under a team hangs under."""
        return f"alias:{team_id}:{resource_id}"

    @staticmethod
    def _task_row_id(parent_item: str, task_id: str, index: int) -> str:
        """
        The tree id a task row hangs under.

        The 'task:' prefix keeps it out of every id space the grid keys
        on - a task row is drawn, never edited, marked or dragged - and
        carrying the parent's iid lets one task sit under several rows
        without the iids colliding. The index tells apart a cost
        resource's repeat lines on one task.
        """
        return f"task:{parent_item}:{task_id}:{index}"

    @staticmethod
    def _is_task_row(item: str) -> bool:
        """Whether a tree id is a task row rather than an entity."""
        return isinstance(item, str) and item.startswith('task:')

    @staticmethod
    def _is_alias_row(item: str) -> bool:
        """Whether a tree id is a team's member lens row."""
        return isinstance(item, str) and item.startswith('alias:')

    def _canonical_id(self, item: str) -> Optional[str]:
        """
        The pool id a row stands for, following aliases to their member.

        An alias row is the member resource seen through its team, so an
        action aimed at it is aimed at the member - which is why it
        resolves rather than returning None.
        """
        if item is None or self._is_task_row(item):
            return None
        if self._is_alias_row(item):
            return item.rsplit(':', 1)[-1]
        return item.split(':', 1)[1]

    def _entity_by_id(self, entity_id: str):
        """The pool entity an id names, whatever its kind."""
        repo = self.project.resource_repository
        return (repo.resources.get(entity_id)
                or repo.teams.get(entity_id)
                or repo.materials.get(entity_id)
                or repo.costs.get(entity_id))

    def _entity_for_row(self, item: str):
        """The pool entity a canonical or alias row stands for."""
        entity_id = self._canonical_id(item)
        return self._entity_by_id(entity_id) if entity_id else None

    def _team_members(self, team: TeamPool) -> List[Resource]:
        """The resources carrying this team's membership, by name."""
        members = [r for r in
                   self.project.resource_repository.resources.values()
                   if r.team_memberships.get(team.id, 0.0) > 0]
        return sorted(members, key=lambda r: r.name.lower())

    # ------------------------------------------------------------------
    # What a row shows
    # ------------------------------------------------------------------

    def _row_values(self, entity, type_label: str) -> tuple:
        """The data cells of one entity row, in COLUMNS order."""
        task_ids = self._entity_task_ids(entity.id)
        committed = self._committed_text(entity)
        detail = self._detail_text(entity)
        if task_ids:
            mean = sum(
                (self.project.get_task_by_id(t).progress or 0)
                for t in task_ids
                if self.project.get_task_by_id(t) is not None
            ) / max(len(task_ids), 1)
            progress = 'Σ ' + self._progress_text(mean)
        else:
            progress = ''
        return (
            type_label,
            getattr(entity, 'initials', '') or '',
            getattr(entity, 'group', '') or '',
            detail,
            f"{len(task_ids)} task(s)" if task_ids else '',
            committed,
            progress,
        )

    def _alias_row_values(self, member: Resource, team: TeamPool) -> tuple:
        """The cells a member's italic lens row under a team shows."""
        ratio = member.team_memberships.get(team.id, 0.0)
        type_label = ('Named' if member.resource_type == ResourceType.NAMED
                      else 'Generic')
        return (
            type_label,
            member.initials,
            '',
            f"{ratio * 100:g}% of {team.name}",
            '',
            '',
            '',
        )

    def _task_row_values(self, task: Task, assignment: dict,
                         entity) -> tuple:
        """
        The cells a task row shows, in COLUMNS order.

        Read-only by design: the row answers "what is this entity working
        on and how done is it" - the task's own type and percentage, and
        in Detail what this particular assignment is worth to it.
        """
        kind = assignment.get('kind')
        if kind == 'cost':
            detail = f"${float(assignment.get('cost', 0.0)):g}"
        elif kind == 'material':
            detail = str(assignment.get('units', '1'))
            label = getattr(entity, 'material_label', '') or ''
            if label:
                detail += f" {label}"
        else:
            detail = f"{float(assignment.get('resource_split', 100.0)):g}%"
        return (
            getattr(task, 'task_type', '') or '',
            '',
            '',
            detail,
            '',
            '',
            self._progress_text(task.progress),
        )

    @staticmethod
    def _progress_text(progress) -> str:
        """The bar and percentage the Progress cell shows."""
        progress = max(0, min(100, int(progress or 0)))
        filled = int(round(progress / 100 * BAR_CELLS))
        bar = BAR_FILL * filled + BAR_EMPTY * (BAR_CELLS - filled)
        return f"{bar} {progress}%"

    def _detail_text(self, entity) -> str:
        """The one-line description of what kind of entity this is."""
        if isinstance(entity, TeamPool):
            members = len(self._team_members(entity))
            return f"{members} member(s)" if members else 'no members'
        if isinstance(entity, MaterialResource):
            return entity.material_label or 'material'
        if isinstance(entity, CostResource):
            return f"accrues at {entity.accrue_at.value.lower()}"
        return entity.role_type or ''

    def _committed_text(self, entity) -> str:
        """
        What the pool has promised to this entity across the plan.

        Hours for work entities - the sum of every assignment's estimated
        hours scaled by its split, the same figure the matrix's cells
        draw from. A quantity for materials, a dollar total for cost
        resources.
        """
        total_hours = 0.0
        total_quantity = 0.0
        total_cost = 0.0
        hpd = getattr(self.project, 'hours_per_day',
                      eff.DEFAULT_HOURS_PER_DAY)
        for task in self.project.tasks:
            duration = (task.end_date - task.start_date).days \
                if task.start_date and task.end_date else 0
            for assignment in task.resource_assignments:
                if assignment.get('resource_id') != entity.id:
                    continue
                kind = assignment.get('kind')
                if kind == 'cost':
                    total_cost += float(assignment.get('cost', 0.0))
                elif kind == 'material':
                    total_quantity += material_quantity(
                        str(assignment.get('units', '0')), duration, hpd)
                else:
                    total_hours += float(
                        assignment.get('estimated_hours', 0.0)) * float(
                        assignment.get('resource_split', 100.0)) / 100.0
        if isinstance(entity, CostResource):
            return f"${total_cost:g}" if total_cost else ''
        if isinstance(entity, MaterialResource):
            label = entity.material_label or 'units'
            return f"{total_quantity:g} {label}" if total_quantity else ''
        return f"{total_hours:g}h" if total_hours else ''

    def _entity_task_ids(self, entity_id: str) -> List[str]:
        """The ids of the tasks carrying an assignment for this entity."""
        return [task.id for task in self.project.tasks
                if any(a.get('resource_id') == entity_id
                       for a in task.resource_assignments)]

    def _entity_assignments(self, task: Task, entity_id: str) -> List[dict]:
        """The assignment entries of this entity on one task, in order."""
        return [a for a in task.resource_assignments
                if a.get('resource_id') == entity_id]

    def _insert_task_rows(self, parent_item: str, entity_id: str) -> None:
        """Draw the entity's assigned tasks as read-only child rows."""
        entity = self._entity_by_id(entity_id)
        if entity is None:
            return
        for task in self.project.tasks:
            entries = self._entity_assignments(task, entity_id)
            for index, assignment in enumerate(entries):
                self.tree.insert(
                    parent_item, tk.END,
                    iid=self._task_row_id(parent_item, task.id, index),
                    text=task.name or '(unnamed)', open=True,
                    values=self._task_row_values(task, assignment,
                                                 entity))

    def _paint_rows(self) -> None:
        """Give every visible row its band - and aliases their slant."""
        try:
            rows = self._rows_in_display_order()
        except tk.TclError:
            return

        for index, item in enumerate(rows):
            band = 'oddrow' if index % 2 else 'evenrow'
            if self._is_alias_row(item):
                # A member seen through its team keeps the banding but
                # reads in italic - a lens onto the row's own section.
                self.tree.item(item, tags=(band, 'alias'))
            else:
                self.tree.item(item, tags=(band,))

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def _heading_clicked(self, column: str) -> None:
        """Sort by a column; a second click on it flips the direction."""
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self.refresh()

    def _sorted_entities(self, entities: List) -> List:
        """A section's rows in the order the last heading click set."""
        if not self._sort_column:
            return entities

        def key(entity):
            column = self._sort_column
            if column == '#0':
                return entity.name.lower()
            if column == 'Type':
                return type(entity).__name__.lower()
            if column == 'Initials':
                return getattr(entity, 'initials', '') or ''
            if column == 'Group':
                return getattr(entity, 'group', '') or ''
            if column == 'Detail':
                return self._detail_text(entity).lower()
            if column == 'Tasks':
                return len(self._entity_task_ids(entity.id))
            if column == 'Committed':
                return self._committed_text(entity)
            if column == 'Progress':
                ids = self._entity_task_ids(entity.id)
                if not ids:
                    return -1
                return sum((self.project.get_task_by_id(t).progress or 0)
                           for t in ids
                           if self.project.get_task_by_id(t)) / len(ids)
            return entity.name.lower()

        return sorted(entities, key=key, reverse=self._sort_reverse)

    # ------------------------------------------------------------------
    # Marks - the gutter checkboxes
    # ------------------------------------------------------------------

    def _mark_for(self, item: str) -> str:
        """The glyph a row's box shows; aliases share the member's."""
        entity_id = self._canonical_id(item)
        return MARK_SET if entity_id in self._marked else MARK_NONE

    def _toggle_mark(self, item: str) -> None:
        """Tick or un-tick a row; an alias ticks the member it mirrors."""
        entity_id = self._canonical_id(item)
        if entity_id is None:
            return
        if entity_id in self._marked:
            self._marked.discard(entity_id)
        else:
            self._marked.add(entity_id)
        self._refresh_gutter()

    def _on_gutter_click(self, event) -> str:
        """A click in the gutter toggles the row's mark."""
        item = self.id_tree.identify_row(event.y)
        if item and not self._is_task_row(item):
            self._toggle_mark(item)
            self._say(f"{len(self._marked)} row(s) marked.")
        return 'break'

    def marked_ids(self) -> List[str]:
        """The marked entity ids, in display order."""
        order = [self._canonical_id(item)
                 for item in self._rows_in_display_order()]
        return [i for i in order if i in self._marked]

    def _actionable_ids(self, clicked: Optional[str] = None) -> List[str]:
        """
        What a bulk action acts on: the marks when any exist, else the
        selection, else the row the menu was opened on.
        """
        marked = self.marked_ids()
        if marked:
            return marked
        selected = [self._canonical_id(i) for i in self.tree.selection()]
        selected = [i for i in selected if i is not None]
        if selected:
            return selected
        if clicked:
            entity_id = self._canonical_id(clicked)
            if entity_id is not None:
                return [entity_id]
        return []

    # ------------------------------------------------------------------
    # The gutter and scroll
    # ------------------------------------------------------------------

    def _rows_in_display_order(self) -> List[str]:
        """The row ids the grid is showing, top to bottom."""
        ordered = []

        def walk(parent=''):
            for item in self.tree.get_children(parent):
                ordered.append(item)
                walk(item)

        walk()
        return ordered

    def _refresh_gutter(self) -> None:
        """Redraw the gutter so it mirrors the visible rows."""
        gutter = getattr(self, 'id_tree', None)
        if gutter is None or not gutter.winfo_exists():
            return
        try:
            gutter.delete(*gutter.get_children(''))
        except tk.TclError:
            return

        task_numbers = self.project.display_ids()
        width = self.project.ID_WIDTH
        number = 0
        for item in self._rows_in_display_order():
            if self._is_task_row(item):
                # A task row carries the task's own number and no box -
                # marks are an entity thing.
                task_id = item.rsplit(':', 2)[-2]
                label = str(task_numbers.get(task_id, '')).zfill(width)
                gutter.insert('', tk.END, iid=item, text=f"{label}")
                continue
            if self._is_alias_row(item):
                # A lens row has no number of its own and takes no mark
                # of its own - the member's row carries both.
                gutter.insert('', tk.END, iid=item, text='')
                continue
            number += 1
            label = str(number).zfill(width)
            gutter.insert('', tk.END, iid=item,
                          text=f"{label} {self._mark_for(item)}")

        try:
            gutter.yview_moveto(self.tree.yview()[0])
        except (tk.TclError, IndexError):
            pass

    def _rows_scrolled(self, first, last) -> None:
        """Move the scrollbar and keep the gutter in step."""
        gutter = getattr(self, 'id_tree', None)
        if gutter is not None:
            try:
                gutter.yview_moveto(first)
            except tk.TclError:
                pass
        if getattr(self, '_vertical_scrollbar', None) is not None:
            self._vertical_scrollbar.set(first, last)

    def _gutter_wheel(self, event) -> str:
        """Route a wheel roll over the gutter to the grid beside it."""
        if getattr(event, 'num', 0) == 4:
            self.tree.yview_scroll(-1, 'units')
        elif getattr(event, 'num', 0) == 5:
            self.tree.yview_scroll(1, 'units')
        else:
            self.tree.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def _capture_view_state(self) -> dict:
        """Selection, folds and scroll, before a rebuild tears them down."""
        try:
            return {
                'selection': tuple(self.tree.selection()),
                'focus': self.tree.focus(),
                'closed': {item for item in self._rows_in_display_order()
                           if not self.tree.item(item, 'open')},
                'scroll': self.tree.yview()[0],
            }
        except tk.TclError:
            return {}

    def _restore_view_state(self, state: dict) -> None:
        """Put the selection, folds and scroll back after a rebuild."""
        if not state:
            return
        try:
            for item in state.get('closed', ()):
                if self.tree.exists(item):
                    self.tree.item(item, open=False)
            alive = [i for i in state.get('selection', ())
                     if self.tree.exists(i)]
            if alive:
                self.tree.selection_set(*alive)
            focused = state.get('focus')
            if focused and self.tree.exists(focused):
                self.tree.focus(focused)
            scroll = state.get('scroll')
            if scroll is not None:
                self.tree.yview_moveto(scroll)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Creating and editing entities - the settings window's own editors
    # ------------------------------------------------------------------

    def _open_new_menu(self, button) -> None:
        """The choices under the header's + New button."""
        menu = tk.Menu(self, tearoff=0)
        for label, kind in (('Named Resource', 'named'),
                            ('Generic Resource', 'generic'),
                            ('Team', 'team'),
                            ('Material', 'material'),
                            ('Cost', 'cost')):
            menu.add_command(
                label=label,
                command=lambda k=kind: self.create_entity(k))
        try:
            menu.tk_popup(button.winfo_rootx(),
                          button.winfo_rooty() + button.winfo_height())
        finally:
            menu.grab_release()

    def create_entity(self, kind: str) -> None:
        """
        Open the editor for a new pool entity of the chosen kind.

        The modal is the resource settings window's own: the fields and
        the validation are the ones the reader already knows, and the
        write it makes on Save is recorded against the undo history by
        _record_pool_change.
        """
        self._open_entity_editor(kind, None)

    def _open_entity_editor(self, kind: str, entity) -> None:
        """Open the matching editor modal, tracking what it changes."""
        from gantt_app.views import resourcesettings
        repo = self.project.resource_repository
        before = repo.to_dict()
        master = self.winfo_toplevel()

        if kind in ('named', 'generic'):
            modal = resourcesettings.ResourceEditorModal(
                master, repo, resource=entity,
                on_apply=lambda _id, b=before: self._record_pool_change(
                    b, 'Edit Resource' if entity else 'New Resource'))
            if entity is None and kind == 'generic':
                # The editor opens Named by default; a generic new row
                # starts as the placeholder type instead.
                modal.type_menu.set(
                    resourcesettings.TYPE_LABELS[ResourceType.GENERIC])
                modal._type_changed()
        elif kind == 'team':
            resourcesettings.TeamEditorModal(
                master, repo, team=entity,
                on_apply=lambda _id, b=before: self._record_pool_change(
                    b, 'Edit Team' if entity else 'New Team'))
        elif kind == 'material':
            resourcesettings.MaterialEditorModal(
                master, repo, material=entity,
                on_apply=lambda _id, b=before: self._record_pool_change(
                    b, 'Edit Material' if entity else 'New Material'))
        elif kind == 'cost':
            resourcesettings.CostEditorModal(
                master, repo, cost=entity,
                on_apply=lambda _id, b=before: self._record_pool_change(
                    b, 'Edit Cost' if entity else 'New Cost'))

    def _record_pool_change(self, before: dict, label: str) -> None:
        """Record an editor modal's write as one undoable step."""
        if self.project_tracker:
            changed = self.project_tracker.record_resource_pool_change(
                before, label)
        else:
            changed = (
                self.project.resource_repository.to_dict() != before)
        if changed:
            logger.info("Pool changed via usage grid: %s", label)
            self._say(f"{label} applied.")
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def _editor_kind(self, entity) -> Optional[str]:
        """Which modal an entity takes, by class."""
        if isinstance(entity, TeamPool):
            return 'team'
        if isinstance(entity, MaterialResource):
            return 'material'
        if isinstance(entity, CostResource):
            return 'cost'
        if isinstance(entity, Resource):
            return ('generic'
                    if entity.resource_type == ResourceType.GENERIC
                    else 'named')
        return None

    # ------------------------------------------------------------------
    # Deleting
    # ------------------------------------------------------------------

    def delete_entities(self, entity_ids) -> None:
        """
        Delete the chosen entities, pruning their task assignments.

        The write is a pool change and a task change in one - removing
        'Anna' also strips her id out of every task's assignments - so it
        runs through run_as_command, whose snapshot covers both
        collections, rather than the pool-only command.
        """
        ids = [i for i in dict.fromkeys(entity_ids)
               if self._entity_by_id(i) is not None]
        if not ids:
            return

        names = [self._entity_by_id(i).name for i in ids]
        assigned = sum(len(self._entity_task_ids(i)) for i in ids)
        if len(ids) == 1:
            prompt = f"Delete '{names[0]}'?"
        else:
            prompt = f"Delete {len(ids)} selected resource(s)?"
        if assigned:
            prompt += (f"\n\n{assigned} task assignment(s) will be "
                       f"removed with it.")
        prompt += "\n\nThis can be undone."

        if not messagebox.askyesno('Delete Resource', prompt,
                                   icon=messagebox.WARNING):
            return

        def apply() -> bool:
            repo = self.project.resource_repository
            changed = False
            for entity_id in ids:
                if entity_id in repo.resources:
                    repo.remove_resource(entity_id)
                    changed = True
                elif entity_id in repo.teams:
                    repo.remove_team(entity_id)
                    changed = True
                elif entity_id in repo.materials:
                    repo.remove_material(entity_id)
                    changed = True
                elif entity_id in repo.costs:
                    repo.remove_cost(entity_id)
                    changed = True
                for task in self.project.tasks:
                    kept = [a for a in task.resource_assignments
                            if a.get('resource_id') != entity_id]
                    if len(kept) != len(task.resource_assignments):
                        task.resource_assignments = kept
                        changed = True
            return changed

        if self.project_tracker:
            changed = self.project_tracker.run_as_command(
                apply, 'Delete Resources')
        else:
            changed = apply()

        if changed:
            logger.info("Deleted %d pool entit(ies): %s",
                        len(ids), names)
            self._marked -= set(ids)
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    # ------------------------------------------------------------------
    # Assigning tasks
    # ------------------------------------------------------------------

    def _open_task_picker(self, entity_ids) -> None:
        """
        Open the task checklist for the row - or the marked rows - it was
        asked for.

        Drawn as a small copy of the task list: the same Treeview style,
        the plan's own indent and expanders, and a [ ] / [x] mark column
        like the gutter's - the deliverables board's picker, pointed at
        the pool instead of the deliverables list.
        """
        entities = [self._entity_by_id(i) for i in
                    dict.fromkeys(entity_ids)]
        entities = [e for e in entities if e is not None]
        if not entities:
            return
        tasks = self.project.display_order()
        if not tasks:
            self._say('There are no tasks to assign yet.')
            return

        # A task counts as "already assigned" only when every edited
        # entity is on it - anything else arrives unticked and is applied
        # to all.
        ticked = set(self._entity_task_ids(entities[0].id))
        for entity in entities[1:]:
            ticked &= set(self._entity_task_ids(entity.id))
        checked: Set[str] = set(ticked)

        window = ctk.CTkToplevel(self.winfo_toplevel())
        if len(entities) == 1:
            window.title(f"Assign Tasks - {entities[0].name}")
        else:
            window.title(f'Assign Tasks to {len(entities)} Resources')
        window.geometry('640x420')
        window.transient(self.winfo_toplevel())

        search = ctk.CTkEntry(window, placeholder_text='Filter tasks…')
        search.pack(fill=tk.X, padx=12, pady=(12, 6))

        tree_frame = ctk.CTkFrame(window, fg_color='transparent')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        tree = ttk.Treeview(
            tree_frame, columns=('Sel', 'No', 'Type', 'Progress'),
            show='tree headings', selectmode='browse')
        theme.style_treeview('Deliverables.Treeview',
                             row_height=self.GRID_ROW_HEIGHT)
        ttk.Style().configure('Deliverables.Treeview', indent=24)
        tree.configure(style='Deliverables.Treeview')
        tree.heading('#0', text='Task', anchor=tk.W)
        tree.heading('Sel', text='', anchor=tk.CENTER)
        tree.heading('No', text='No', anchor=tk.W)
        tree.heading('Type', text='Type', anchor=tk.W)
        tree.heading('Progress', text='Progress', anchor=tk.W)
        tree.column('#0', width=280, minwidth=120)
        tree.column('Sel', width=40, minwidth=40, stretch=False,
                    anchor=tk.CENTER)
        tree.column('No', width=50, minwidth=40, stretch=False)
        tree.column('Type', width=80, minwidth=60, stretch=False)
        tree.column('Progress', width=80, minwidth=60, stretch=False)

        tree.tag_configure('evenrow',
                           background=theme.now(theme.GRID_ROW_BG))
        tree.tag_configure('oddrow',
                           background=theme.now(theme.GRID_ROW_ALT))
        try:
            base = tkfont.nametofont('TkDefaultFont')
            tree.tag_configure(
                'parent',
                font=(base.cget('family'), base.cget('size'), 'bold'))
        except tk.TclError:
            pass        # no display font to derive from; parents stay plain

        numbers = self.project.display_ids()
        task_by_id = {task.id: task for task in tasks}
        known = set(task_by_id)
        parents = {t.parent_task_id for t in tasks if t.parent_task_id}

        def mark(task_id: str) -> str:
            return MARK_SET if task_id in checked else MARK_NONE

        def draw(filter_text: str = '') -> None:
            tree.delete(*tree.get_children())
            wanted = filter_text.strip().lower()

            # A match keeps its ancestors on screen - the same rule the
            # grid's own filter keeps, so the outline never orphans a row.
            if wanted:
                shown_ids = set()
                for task in tasks:
                    haystack = f"{numbers.get(task.id, '')} " \
                               f"{task.name or ''} {task.task_type}"
                    if wanted in haystack.lower():
                        current = task
                        while current is not None \
                                and current.id not in shown_ids:
                            shown_ids.add(current.id)
                            current = task_by_id.get(
                                current.parent_task_id)
            else:
                shown_ids = known

            drawn = 0
            for task in tasks:
                if task.id not in shown_ids:
                    continue
                parent = task.parent_task_id \
                    if task.parent_task_id in shown_ids else ''
                tags = ['evenrow' if drawn % 2 == 0 else 'oddrow']
                if task.id in parents:
                    tags.append('parent')
                tree.insert(
                    parent, tk.END, iid=task.id, open=True,
                    text=task.name or '(unnamed)', tags=tuple(tags),
                    values=(
                        mark(task.id),
                        str(numbers.get(task.id, '')),
                        task.task_type,
                        f'{task.progress}%',
                    ))
                drawn += 1

        def toggle(task_id: str) -> None:
            if task_id in checked:
                checked.discard(task_id)
            else:
                checked.add(task_id)
            if tree.exists(task_id):
                values = list(tree.item(task_id, 'values'))
                values[0] = mark(task_id)
                tree.item(task_id, values=values)

        def on_click(event) -> Optional[str]:
            if tree.identify_region(event.x, event.y) \
                    not in ('cell', 'tree'):
                return None
            if tree.identify_element(event.x, event.y) \
                    == 'Treeitem.indicator':
                return None     # the expander still folds the branch
            item = tree.identify_row(event.y)
            if not item:
                return None
            # The [ ]/[x] cell is the mark gesture, like the grid's
            # gutter; a click on any other cell of the row means the
            # same here.
            toggle(item)
            return 'break'

        tree.bind('<Button-1>', on_click)
        tree.bind('<space>',
                  lambda _e: toggle(tree.focus()) if tree.focus() else None)
        tree.bind('<Return>',
                  lambda _e: toggle(tree.focus()) if tree.focus() else None)
        search.bind('<KeyRelease>', lambda _e: draw(search.get()))
        draw()

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        buttons = ctk.CTkFrame(window, fg_color='transparent')
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))

        def apply() -> None:
            window.destroy()
            self._assign_tasks([e.id for e in entities], set(checked))

        ctk.CTkButton(buttons, text='All', width=64,
                      command=lambda: (checked.update(
                          t.id for t in tasks), draw(search.get()))
                      ).pack(side=tk.LEFT)
        ctk.CTkButton(buttons, text='None', width=64,
                      command=lambda: (checked.clear(),
                                       draw(search.get()))
                      ).pack(side=tk.LEFT, padx=(6, 0))
        ctk.CTkButton(buttons, text='Assign', width=90,
                      command=apply).pack(side=tk.RIGHT, padx=(6, 0))
        ctk.CTkButton(buttons, text='Cancel', width=90,
                      command=window.destroy).pack(side=tk.RIGHT)

        grab_when_visible(window)

    def _assign_tasks(self, entity_ids, task_ids: Set[str]) -> None:
        """
        Make each given entity's membership exactly the chosen task set,
        as one undoable step.

        The entry an added task gets depends on the entity's kind: a cost
        resource asks its amount once and spreads it over every new task;
        a material lands at one unit; a person or team lands at 100% with
        the effort maths the board runs - the seeded zero hours are what
        let the engine see the roster change on an effort-driven task.
        """
        entities = [self._entity_by_id(i) for i in
                    dict.fromkeys(entity_ids)]
        entities = [e for e in entities if e is not None]
        if not entities:
            return
        wanted = set(task_ids)

        # The money on a cost assignment is entered at assign time - the
        # same "Flight $300, Flight $350" rule the board asks with.
        cost_amount = None
        added_any_cost = any(
            isinstance(e, CostResource)
            and wanted - set(self._entity_task_ids(e.id))
            for e in entities)
        if added_any_cost:
            prompt = ('Amount per task:' if len(entities) > 1
                      else f"Amount per task for {entities[0].name}:")
            cost_amount = simpledialog.askfloat(
                'Assign Cost', prompt, minvalue=0.0, parent=self)
            if cost_amount is None:
                return

        hpd = getattr(self.project, 'hours_per_day',
                      eff.DEFAULT_HOURS_PER_DAY)
        updates: Dict[str, dict] = {}

        for entity in entities:
            has = set(self._entity_task_ids(entity.id))
            for task in self.project.tasks:
                # Chain off the pending change when another entity already
                # rewrote this task's list - a bulk assign touching two
                # entities must not drop the first one's entry.
                current = updates.get(task.id, {}).get(
                    'resource_assignments', task.resource_assignments)
                if task.id in wanted and task.id not in has:
                    assignment, duration = self._new_assignment(
                        entity, task, hpd, cost_amount)
                    if assignment is None:
                        continue
                    change = updates.setdefault(task.id, {})
                    change['resource_assignments'] = \
                        [dict(a) for a in current] + [assignment]
                    if duration is not None:
                        change['duration'] = duration
                elif task.id not in wanted and task.id in has:
                    change = updates.setdefault(task.id, {})
                    change['resource_assignments'] = [
                        a for a in current
                        if a.get('resource_id') != entity.id]

        if not updates:
            self._say('Nothing to change.')
            return

        if self.project_tracker:
            changed = self.project_tracker.update_tasks(
                updates, 'Assign Tasks')
        else:
            for task_id, change in updates.items():
                task = self.project.get_task_by_id(task_id)
                for name, value in change.items():
                    setattr(task, name, value)
            changed = True

        if changed:
            logger.info("Assigned task set on %d entit(ies): %s",
                        len(entities),
                        {e.name: sorted(wanted) for e in entities})
            self._say(f"Assignments updated on "
                      f"{len(updates)} task(s).")
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def _new_assignment(self, entity, task: Task, hpd: float,
                      cost_amount):
        """
        The entry a task gains for this entity, and its new duration.

        Returns (assignment, duration) - duration None when the task's
        length is not this change's to move. Work kinds run the effort
        maths the board runs: an effort-driven task with a roster already
        gets shorter as a new pair of hands lands.
        """
        if isinstance(entity, CostResource):
            return ({
                'resource_id': entity.id,
                'kind': 'cost',
                'cost': float(cost_amount or 0.0),
                'actual_cost': 0.0,
            }, None)
        if isinstance(entity, MaterialResource):
            return ({
                'resource_id': entity.id,
                'kind': 'material',
                'units': '1',
            }, None)

        effort = sum(float(a.get('estimated_hours', 0.0))
                     for a in task.resource_assignments) or 8.0
        old_state = eff.state_from_task(task, hpd)
        managed = (eff.logic_applies(old_state) and not task.is_container
                   and old_state.total_units > 0)

        probe = copy.copy(task)
        probe.resource_assignments = [dict(a)
                                      for a in task.resource_assignments]
        probe.resource_assignments.append({
            'resource_id': entity.id,
            'estimated_hours': 0.0 if managed else effort,
            'resource_split': 100.0,
        })

        duration = task.duration
        if managed:
            new_state = eff.state_from_task(probe, hpd)
            _result, conflict = eff.reconcile(old_state, new_state)
            if conflict is None:
                eff.write_state_to_task(new_state, probe, hpd)
                duration = probe.duration
        return probe.resource_assignments[-1], duration

    def _unassign_task(self, item: str) -> None:
        """Take the one assignment a task row stands for off its entity."""
        _tag, parent_item, task_id, index = item.rsplit(':', 3)
        entity = self._entity_for_row(parent_item)
        task = self.project.get_task_by_id(task_id)
        if entity is None or task is None:
            return

        entries = [i for i, a in enumerate(task.resource_assignments)
                   if a.get('resource_id') == entity.id]
        try:
            position = entries[int(index)]
        except (IndexError, ValueError):
            return

        new_list = [a for i, a in enumerate(task.resource_assignments)
                    if i != position]
        if self.project_tracker:
            self.project_tracker.update_task(
                task_id=task.id, resource_assignments=new_list)
        else:
            task.resource_assignments = new_list
        logger.info("Removed %r's assignment from task %s (%s)",
                    entity.name, task.id, task.name)
        self._say(f"Removed {task.name} from {entity.name}.")
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    # ------------------------------------------------------------------
    # The menus
    # ------------------------------------------------------------------

    def _bind_context_menu(self) -> None:
        """Bind the platform's context-menu gesture to the grid."""
        try:
            windowing = self.tree.tk.call('tk', 'windowingsystem')
        except tk.TclError:
            windowing = 'x11'
        if windowing == 'aqua':
            self.tree.bind('<Button-2>', self._on_context_click)
            self.tree.bind('<Control-Button-1>', self._on_context_click)
        else:
            self.tree.bind('<Button-3>', self._on_context_click)

    def _on_context_click(self, event) -> str:
        """Open the menu on the row under the pointer."""
        item = self.tree.identify_row(event.y)
        if item and item not in self.tree.selection():
            self.tree.selection_set(item)
        self._open_context_menu(item, event.x_root, event.y_root)
        return 'break'

    def _open_context_menu(self, item, x_root, y_root) -> None:
        """Build and post the menu for the row it was opened on."""
        if item and self._is_task_row(item):
            self._open_task_row_menu(item, x_root, y_root)
            return
        menu = tk.Menu(self.tree, tearoff=0)
        entity = self._entity_for_row(item) if item else None
        chosen = self._actionable_ids(item)

        new_menu = tk.Menu(menu, tearoff=0)
        for label, kind in (('Named Resource', 'named'),
                            ('Generic Resource', 'generic'),
                            ('Team', 'team'),
                            ('Material', 'material'),
                            ('Cost', 'cost')):
            new_menu.add_command(
                label=label,
                command=lambda k=kind: self.create_entity(k))
        menu.add_cascade(label='New', menu=new_menu)

        menu.add_command(
            label='Edit…',
            state=(tk.NORMAL if entity is not None else tk.DISABLED),
            command=lambda: self._open_entity_editor(
                self._editor_kind(entity), entity))
        menu.add_separator()

        menu.add_command(
            label='Assign Tasks…',
            state=(tk.NORMAL if chosen else tk.DISABLED),
            command=lambda: self._open_task_picker(chosen))
        if entity is not None:
            task_rows = [self.project.get_task_by_id(t)
                         for t in self._entity_task_ids(entity.id)]
            if any(t is not None for t in task_rows):
                remove_menu = tk.Menu(menu, tearoff=0)
                for task in task_rows:
                    if task is None:
                        continue
                    remove_menu.add_command(
                        label=f"☑ {task.name or '(unnamed)'}",
                        command=lambda t=task: self._unassign_entity(
                            entity.id, t.id))
                menu.add_cascade(label='Remove Task', menu=remove_menu)
        menu.add_separator()

        if item and not self._is_alias_row(item):
            marked = self._canonical_id(item) in self._marked
            menu.add_command(
                label='Unmark' if marked else 'Mark',
                command=lambda: self._toggle_mark(item))
        menu.add_command(
            label='Delete',
            state=(tk.NORMAL if chosen else tk.DISABLED),
            command=lambda: self.delete_entities(chosen))
        menu.add_separator()

        manager = getattr(self.project_tracker, 'manager', None)
        menu.add_command(
            label='Undo',
            state=(tk.NORMAL if manager and manager.can_undo()
                   else tk.DISABLED),
            command=self._undo)
        menu.add_command(
            label='Redo',
            state=(tk.NORMAL if manager and manager.can_redo()
                   else tk.DISABLED),
            command=self._redo)

        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _unassign_entity(self, entity_id: str, task_id: str) -> None:
        """Strip every entry of one entity from one task - the submenu's
        one-click remove."""
        task = self.project.get_task_by_id(task_id)
        if task is None:
            return
        new_list = [a for a in task.resource_assignments
                    if a.get('resource_id') != entity_id]
        if len(new_list) == len(task.resource_assignments):
            return
        if self.project_tracker:
            self.project_tracker.update_task(
                task_id=task.id, resource_assignments=new_list)
        else:
            task.resource_assignments = new_list
        entity = self._entity_by_id(entity_id)
        logger.info("Removed task %s from %s", task_id,
                    getattr(entity, 'name', entity_id))
        self.refresh()
        if self.on_project_changed:
            self.on_project_changed()

    def _open_task_row_menu(self, item: str, x_root, y_root) -> None:
        """
        The right-click menu on an assigned-task row: it is display, not
        an entity, so all it offers is the one thing it can change -
        coming off the row it hangs under.
        """
        _tag, parent_item, task_id, _index = item.rsplit(':', 3)
        task = self.project.get_task_by_id(task_id)
        entity = self._entity_for_row(parent_item)
        name = getattr(entity, 'name', 'resource')
        label = (f"Remove '{task.name}' from {name}"
                 if task is not None else 'Remove from resource')
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(label=label,
                         command=lambda: self._unassign_task(item))
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _on_double_click(self, event):
        """Open the editor the clicked row takes."""
        if self.tree.identify_region(event.x, event.y) \
                not in ('cell', 'tree'):
            return None
        item = self.tree.identify_row(event.y)
        if not item or self._is_task_row(item):
            return 'break'      # a task row is read-only display
        entity = self._entity_for_row(item)
        if entity is not None:
            self._open_entity_editor(self._editor_kind(entity), entity)
        return 'break'

    # ------------------------------------------------------------------
    # Undo / status
    # ------------------------------------------------------------------

    def _undo(self) -> None:
        manager = getattr(self.project_tracker, 'manager', None)
        if manager and manager.can_undo() and manager.undo():
            self.refresh()
            if self.on_project_changed:
                self.on_project_changed()

    def _redo(self) -> None:
        manager = getattr(self.project_tracker, 'manager', None)
        if manager and manager.can_redo() and manager.redo():
            self.refresh()
            if self.on_project_changed:
                self.on_project_changed()

    def _say(self, message: str) -> None:
        """Send a line to the footer's status bar, if there is one."""
        if self.on_status:
            self.on_status(message)

    # ------------------------------------------------------------------
    # What the status bar shows
    # ------------------------------------------------------------------
    def selection_status(self) -> Optional[str]:
        """
        The status-bar line for the row under the cursor, or None.

        A task row describes the task; an alias row describes the member,
        naming the team it is seen through; anything else describes the
        pool entity the row stands for.
        """
        selection = self.tree.selection()
        if not selection:
            return None
        item = selection[0]
        if self._is_task_row(item):
            _tag, _parent, task_id, _index = item.rsplit(':', 3)
            task = self.project.get_task_by_id(task_id)
            return task_status_line(task) if task is not None else None
        entity = self._entity_for_row(item)
        if entity is None:
            return None
        via_team = None
        if self._is_alias_row(item):
            parent = self.tree.parent(item)
            team = self._entity_by_id(self._canonical_id(parent))
            via_team = getattr(team, 'name', None)
        return entity_status_line(entity, self.project, via_team=via_team)

    def _push_selection_status(self) -> None:
        """Tell the status bar what is selected now, if it is listening."""
        if self.on_status:
            self.on_status(self.selection_status() or "Ready")

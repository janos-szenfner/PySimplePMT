"""
Copy, Cut, and Paste functionality for the Gantt Project Management Tool.

This module provides a centralized Clipboard Manager Service for handling
copy, cut, and paste operations for both single and multiple items via
keyboard shortcuts and right-click context menu.

The implementation follows the architectural design with a standardized
ClipboardPayload model that supports both application clipboard state
and system clipboard integration.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
import copy
import json

from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from gantt_app.models import Project, Task


#: Supported entity types for clipboard operations
ENTITY_TYPES = ('task', 'deliverable', 'phase', 'subtask', 'milestone')

#: Container types that can accept pasted items
CONTAINER_TYPES = ('phase', 'deliverable', 'task')

#: What separates the readable summary on the desktop clipboard from the
#: JSON after it. See ClipboardService._clipboard_text.
CLIPBOARD_MARKER = '\n--- PySimplePMT tasks ---\n'

#: What each kind of item may be pasted into, by the type of the row it
#: would go under. An empty tuple means the top level and nowhere else.
#:
#: The plan runs Phase, Deliverable, Task, Subtask, and pasting is held to
#: that: a phase is a top-level scope and does not go inside a task, a
#: sub-task belongs to a task and to nothing else. Paste is greyed out on
#: the menu where this says no, rather than being offered and then refused.
#:
#: A Task may go under a Task. Sub-tasks are the usual thing to find there,
#: but a plan nested deeper than the four levels is one this application has
#: always allowed and imported files arrive carrying.
ALLOWED_PARENT_TYPES = {
    'phase': (),
    'deliverable': ('phase',),
    'task': ('phase', 'deliverable', 'task'),
    'subtask': ('task',),
    'milestone': ('phase', 'deliverable', 'task'),
}


@dataclass
class ClipboardItem:
    """
    Represents a single item in the clipboard payload.
    
    Attributes:
        id: Unique identifier for the item
        type: Entity type (e.g., 'task', 'deliverable')
        payload: Deep copy of the original entity properties
    """
    id: str
    type: str
    payload: Dict[str, Any]


@dataclass
class ClipboardPayload:
    """
    Standardized data transfer payload structure for clipboard operations.
    
    This model ensures that items are stored with their underlying IDs,
    entity types, and original parent/container context for validation
    during paste or cut cleanup operations.
    
    Attributes:
        operation: The clipboard operation type ('copy' or 'cut')
        source_container_id: ID of the source container/parent
        items: Array of ClipboardItem objects
    """
    operation: str  # 'copy' or 'cut'
    source_container_id: Optional[str] = None
    items: List[ClipboardItem] = field(default_factory=list)


class ClipboardService:
    """
    Centralized service for managing copy, cut, and paste operations.
    
    This service maintains an in-memory application clipboard state
    and handles integration with the system clipboard for cross-application
    copy/paste support.
    
    The service works with the Project model to manage tasks and their
    hierarchical relationships.
    
    Attributes:
        project: Reference to the Project model
        active_payload: Current clipboard payload (in-memory state)
        cut_item_ids: Set of item IDs that are in cut state (pending relocation)
    """
    
    def __init__(self, project: Optional['Project'] = None):
        """
        Initialize the ClipboardService.
        
        Args:
            project: The Project model instance
        """
        self.project = project
        self.active_payload: Optional[ClipboardPayload] = None
        self.cut_item_ids: Set[str] = set()
        #: Any Tk widget, used only to reach the desktop clipboard. Without
        #: one this window's own clipboard still works.
        self.clipboard_widget = None
        
    def get_selected_ids(self) -> List[str]:
        """
        Get the array of currently selected item IDs.
        
        This should be connected to the application's selection state.
        For now, returns an empty list - should be implemented by the UI.
        
        Returns:
            List[str]: Array of selected entity IDs
        """
        return []
    
    def copy(self, selected_ids: Optional[List[str]] = None) -> None:
        """
        Copy selected items to the clipboard.
        
        Args:
            selected_ids: Array of entity IDs to copy. If None, uses currently selected IDs.
        
        Process:
            1. Fetch full entity objects for all selected IDs.
            2. Clear any prior cut visual state on existing elements.
            3. Instantiate a ClipboardPayload with operation='copy'.
            4. Write the payload to the in-memory application clipboard store.
            5. Serialize to system clipboard (if available).
        """
        if selected_ids is None:
            selected_ids = self.get_selected_ids()

        if not self.project:
            logger.warning("Cannot copy: no plan is open")
            return
        if not selected_ids:
            logger.info("Copy did nothing: no rows are selected")
            return

        self.clear_cut_state()
        
        items = []
        for entity_id in selected_ids:
            entity = self._get_task_by_id(entity_id)
            if entity:
                items.append(ClipboardItem(
                    id=entity_id,
                    type=self._get_entity_type(entity),
                    payload=self._task_to_dict(entity)
                ))
        
        if not items:
            logger.warning("Nothing to copy: %s is in no plan", selected_ids)
            return

        first_task = self._get_task_by_id(selected_ids[0])
        source_container_id = first_task.parent_task_id if first_task else None

        logger.info("Copied %d item(s): %s",
                    len(items), [item.id for item in items])
        self.active_payload = ClipboardPayload(
            operation='copy',
            source_container_id=source_container_id,
            items=items
        )
        
        self._write_to_system_clipboard()
    
    def cut(self, selected_ids: Optional[List[str]] = None) -> None:
        """
        Cut selected items to the clipboard.
        
        Args:
            selected_ids: Array of entity IDs to cut. If None, uses currently selected IDs.
        
        Process:
            1. Fetch full entity objects for selected IDs.
            2. Instantiate a ClipboardPayload with operation='cut'.
            3. Write the payload to the in-memory application clipboard store.
            4. Apply visual feedback to cut items (e.g., reduce opacity).
            5. Write serialized JSON to system clipboard.
        """
        if selected_ids is None:
            selected_ids = self.get_selected_ids()

        if not self.project:
            logger.warning("Cannot cut: no plan is open")
            return
        if not selected_ids:
            logger.info("Cut did nothing: no rows are selected")
            return

        self.clear_cut_state()
        
        items = []
        for entity_id in selected_ids:
            entity = self._get_task_by_id(entity_id)
            if entity:
                items.append(ClipboardItem(
                    id=entity_id,
                    type=self._get_entity_type(entity),
                    payload=self._task_to_dict(entity)
                ))
        
        if not items:
            logger.warning("Nothing to cut: %s is in no plan", selected_ids)
            return

        first_task = self._get_task_by_id(selected_ids[0])
        source_container_id = first_task.parent_task_id if first_task else None

        logger.info("Cut %d item(s): %s",
                    len(items), [item.id for item in items])
        self.active_payload = ClipboardPayload(
            operation='cut',
            source_container_id=source_container_id,
            items=items
        )
        
        self.cut_item_ids = set(selected_ids)
        
        self._write_to_system_clipboard()
    
    def paste(self, target_container_id: Optional[str] = None, insert_index: Optional[int] = None) -> List[str]:
        """
        Paste items from the clipboard to the target container.
        
        Args:
            target_container_id: ID of the destination container (parent task ID)
            insert_index: Optional insertion index for the pasted items
        
        Process:
            1. Retrieve payload from in-memory store (or fallback to system clipboard).
            2. Validation: Verify target container allows the entity types.
            3. ID Regeneration: Generate fresh unique IDs for all pasted items.
            4. Persistence & Insertion:
               - If operation='copy': Insert newly created duplicate entities.
               - If operation='cut': Move original items to target container.
            5. State Update: Select the newly pasted items.
        """
        if not self.project:
            logger.warning("Cannot paste: no plan is open")
            return []

        payload = self._resolve_payload()
        if not payload or not payload.items:
            logger.info("Paste did nothing: the clipboard is empty")
            return []

        entity_types = [item.type for item in payload.items]
        if not self._can_accept_types(target_container_id, entity_types):
            logger.info("Refused to paste %s into %s: it does not belong there",
                        entity_types, target_container_id or "the top level")
            return []

        if payload.operation == 'cut' and any(
                self._is_self_or_descendant(target_container_id, item.id)
                for item in payload.items):
            logger.warning(
                "Refused to paste %s into %s: it would sit inside itself",
                [item.id for item in payload.items], target_container_id)
            return []

        where = target_container_id or "the top level"
        logger.info("Pasting %d %s item(s) into %s",
                    len(payload.items), payload.operation, where)

        if payload.operation == 'copy':
            pasted = self._paste_copy(payload, target_container_id, insert_index)
        elif payload.operation == 'cut':
            pasted = self._paste_cut(payload, target_container_id, insert_index)
        else:
            logger.error("Unknown clipboard operation %r; nothing pasted",
                         payload.operation)
            return []

        logger.info("Pasted %s", pasted)
        return pasted
    
    def _paste_copy(self, payload: ClipboardPayload,
                    target_container_id: Optional[str],
                    insert_index: Optional[int] = None) -> List[str]:
        """
        Paste copied items as new tasks under the target.

        DEVELOPMENT NOTES:
        ------------------
        One new task per item on the clipboard, and nothing else. Copying a
        phase copies the phase row; the work under it is not brought along
        and is not duplicated. What is selected is what is copied, so a
        selection that includes both a phase and one of its tasks produces
        exactly those two.

        The new tasks are numbered from the project's own sequence rather
        than given a UUID. The ID is a column in the task list, and a plan
        that reads 001, 002, 4f3c8a91-... in the same table does not.
        """
        if not self.project:
            return []

        new_tasks = []
        for item in payload.items:
            new_task_data = copy.deepcopy(item.payload)
            new_task_data['id'] = self._next_id(new_tasks)
            new_task_data['parent_task_id'] = target_container_id
            
            if payload.source_container_id == target_container_id:
                name = new_task_data.get('name', 'Untitled')
                new_task_data['name'] = f"{name} (Copy)"
            
            new_task = self._dict_to_task(new_task_data)
            new_tasks.append(new_task)
        
        for task in new_tasks:
            self.project.add_task(task)
        return [task.id for task in new_tasks]
    
    def _paste_cut(self, payload: ClipboardPayload,
                   target_container_id: Optional[str],
                   insert_index: Optional[int] = None) -> List[str]:
        """
        Move the cut items under the target.

        RETURNS:
        --------
        List[str]
            The rows that moved, for the caller to select.

        The clipboard is emptied afterwards: a cut is one move, and the
        dimming that marks the rows as pending goes with it.
        """
        if not self.project:
            return []

        moved = []
        for item in payload.items:
            task = self._get_task_by_id(item.id)
            if task:
                task.parent_task_id = target_container_id
                moved.append(task.id)

        self.clear_cut_state()
        self.active_payload = None
        return moved
    
    def clear_cut_state(self) -> None:
        """Clear the cut visual state for all previously cut items."""
        self.cut_item_ids.clear()
    
    def clear_clipboard(self) -> None:
        """Clear the clipboard payload and cut state."""
        self.active_payload = None
        self.clear_cut_state()
    
    def is_clipboard_empty(self) -> bool:
        """Check if the clipboard is empty."""
        return self.active_payload is None or not self.active_payload.items
    
    def can_paste(self, target_container_id: Optional[str] = None) -> bool:
        """Check if paste operation is possible for the target container."""
        if self.is_clipboard_empty():
            return False
        
        payload = self._resolve_payload()
        if not payload or not payload.items:
            return False
        
        entity_types = [item.type for item in payload.items]
        return self._can_accept_types(target_container_id, entity_types)
    
    def can_copy_or_cut(self, selected_ids: Optional[List[str]] = None) -> bool:
        """Check if copy or cut operations are possible."""
        if selected_ids is None:
            selected_ids = self.get_selected_ids()
        return len(selected_ids) > 0
    
    def _resolve_payload(self) -> Optional[ClipboardPayload]:
        """
        The clipboard to paste from: this window's, or the desktop's.

        RETURNS:
        --------
        Optional[ClipboardPayload]
            None when neither holds anything of ours.

        DEVELOPMENT NOTES:
        ------------------
        This window's own comes first. It holds the whole item and whether
        the operation was a cut, which the text on the desktop clipboard
        cannot say as exactly.
        """
        if self.active_payload:
            return self.active_payload

        text = self._read_system_clipboard()
        if not text:
            return None

        _summary, _, encoded = text.rpartition(CLIPBOARD_MARKER)
        if not encoded:
            logger.debug("The desktop clipboard holds text, but not a plan "
                         "of ours")
            return None

        try:
            data = json.loads(encoded)
            return ClipboardPayload(
                operation=data.get('operation', 'copy'),
                source_container_id=data.get('source_container_id'),
                items=[
                    ClipboardItem(id=item['id'], type=item['type'],
                                  payload=item['payload'])
                    for item in data.get('items', [])
                ]
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.debug("The desktop clipboard carries our marker but not "
                         "something that reads back as tasks")
            return None

    def _clipboard_text(self) -> str:
        """
        What to put on the desktop clipboard for the current payload.

        RETURNS:
        --------
        str
            A readable list of what was copied, then a marker line, then the
            same thing as JSON.

        DEVELOPMENT NOTES:
        ------------------
        Both at once, because the two readers want different things. Pasted
        into a mail or a note, the top of it is a list of task names and
        dates somebody can read. Pasted back into this application, the part
        after the marker is what is read, and carries everything a task has.

        Tk's clipboard holds one string per selection, and which MIME types
        a platform will offer alongside it differs by platform - so this is
        one string that answers both rather than two that only work on X11.
        """
        payload = self.active_payload
        lines = [f"{len(payload.items)} item(s) "
                 f"{'cut' if payload.operation == 'cut' else 'copied'} "
                 f"from {self.project.name}:"]
        for item in payload.items:
            name = item.payload.get('name', item.id)
            lines.append(f"  - {name} ({item.type})")

        encoded = json.dumps({
            'operation': payload.operation,
            'source_container_id': payload.source_container_id,
            'items': [
                {'id': item.id, 'type': item.type, 'payload': item.payload}
                for item in payload.items
            ],
        })
        return "\n".join(lines) + f"\n{CLIPBOARD_MARKER}" + encoded

    def _write_to_system_clipboard(self) -> None:
        """
        Put the current payload on the desktop clipboard.

        DEVELOPMENT NOTES:
        ------------------
        Through Tk, which every window here already has, rather than through
        pyperclip. pyperclip was imported and is not a dependency of this
        application, so the import failed every time and was caught every
        time: nothing this application copied ever reached the desktop
        clipboard, and nothing said so.

        Failing to reach it is not worth losing the copy over - the window's
        own clipboard is already written by now - so it is noted and stepped
        over.
        """
        if not self.active_payload or self.clipboard_widget is None:
            return

        try:
            self.clipboard_widget.clipboard_clear()
            self.clipboard_widget.clipboard_append(self._clipboard_text())
        except Exception:
            logger.exception("Could not write to the desktop clipboard")

    def _read_system_clipboard(self) -> str:
        """The desktop clipboard's text, or '' when there is none to read."""
        if self.clipboard_widget is None:
            return ''
        try:
            return self.clipboard_widget.clipboard_get()
        except Exception:
            # Empty, or holding something that is not text at all
            logger.debug("Nothing readable on the desktop clipboard")
            return ''

    def _get_task_by_id(self, task_id: str) -> Optional['Task']:
        """Get task by ID from the project."""
        if self.project:
            return self.project.get_task_by_id(task_id)
        return None
    
    def _get_entity_type(self, task: 'Task') -> str:
        """Get the entity type from a Task object."""
        return task.task_type.lower()
    
    def _next_id(self, pending: List['Task']) -> str:
        """
        The next free task ID, counting the ones about to be added.

        PARAMETERS:
        -----------
        pending : List[Task]
            Tasks built in this paste but not yet in the project, which
            next_task_id cannot see and would otherwise hand out again.
        """
        task_id = self.project.next_task_id()
        taken = {task.id for task in pending}
        while task_id in taken:
            task_id = str(int(task_id) + 1).zfill(len(task_id))
        return task_id

    def _is_self_or_descendant(self, container_id: Optional[str],
                               task_id: str) -> bool:
        """
        Whether a container is the given task, or sits underneath it.

        PARAMETERS:
        -----------
        container_id : Optional[str]
            Where the paste would land. None is the top of the plan, which is
            underneath nothing.
        task_id : str
            The task being moved.

        RETURNS:
        --------
        bool
            True when moving the task there would make it its own ancestor.

        DEVELOPMENT NOTES:
        ------------------
        Cutting a phase and pasting it into one of its own tasks used to be
        allowed. It left a loop in the parent links with no root: the task
        disappeared from the tree, which walks down from the top, and the
        passes that settle the schedule walk that loop.

        The walk is bounded by the number of tasks rather than by reaching
        the top, so a plan that already contains a loop is answered rather
        than followed forever.
        """
        seen = 0
        current = container_id
        while current is not None and seen <= len(self.project.tasks):
            if current == task_id:
                return True
            parent = self._get_task_by_id(current)
            if parent is None:
                return False
            current = parent.parent_task_id
            seen += 1
        return False

    def _can_accept_types(self, container_id: Optional[str],
                          entity_types: List[str]) -> bool:
        """
        Whether a row can hold the kinds of item on the clipboard.

        PARAMETERS:
        -----------
        container_id : Optional[str]
            The row the paste would go under; None is the top of the plan.
        entity_types : List[str]
            The lowercased types being pasted.

        RETURNS:
        --------
        bool
            True only when every one of them belongs there.

        DEVELOPMENT NOTES:
        ------------------
        Every type was accepted by every container. A phase could be pasted
        inside a task, which reads as a task containing a phase of the
        project - and the levels the plan totals its progress through stop
        meaning anything if they can be arranged in any order.
        """
        if container_id is None:
            # The top of the plan takes anything, including a phase, which
            # goes nowhere else
            return True

        container = self._get_task_by_id(container_id)
        if not container:
            logger.info("Cannot paste into %s: no such task", container_id)
            return False

        container_type = container.task_type.lower()
        return all(
            container_type in ALLOWED_PARENT_TYPES.get(
                entity_type.lower(), CONTAINER_TYPES)
            for entity_type in entity_types
        )
    
    def _task_to_dict(self, task: 'Task') -> Dict[str, Any]:
        """Convert a Task object to a dictionary."""
        task_dict = {}
        for key, value in task.__dict__.items():
            if hasattr(value, 'isoformat'):
                task_dict[key] = value.isoformat() if value else None
            elif key == 'dependencies':
                task_dict[key] = [
                    {'task_id': dep.task_id, 'dep_type': dep.dep_type, 
                     'hardness': dep.hardness, 'lag': dep.lag}
                    for dep in value
                ]
            else:
                task_dict[key] = value
        return task_dict
    
    def _dict_to_task(self, task_dict: Dict[str, Any]) -> 'Task':
        """Convert a dictionary back to a Task object."""
        from datetime import datetime
        from gantt_app.models import Task, Dependency
        
        if 'start_date' in task_dict and task_dict['start_date']:
            task_dict['start_date'] = datetime.fromisoformat(task_dict['start_date'])
        if 'end_date' in task_dict and task_dict['end_date']:
            task_dict['end_date'] = datetime.fromisoformat(task_dict['end_date'])
        if 'earliest_begin' in task_dict and task_dict['earliest_begin']:
            task_dict['earliest_begin'] = datetime.fromisoformat(task_dict['earliest_begin'])
        
        if 'dependencies' in task_dict:
            deps = []
            for dep_dict in task_dict['dependencies']:
                dep = Dependency(
                    task_id=dep_dict['task_id'],
                    dep_type=dep_dict.get('dep_type', 'FS'),
                    hardness=dep_dict.get('hardness', 'Hard'),
                    lag=dep_dict.get('lag', 0)
                )
                deps.append(dep)
            task_dict['dependencies'] = deps
        
        return Task(**task_dict)


class ClipboardManager:
    """
    Singleton manager for clipboard operations.
    
    Provides a global access point for clipboard functionality
    and ensures consistent state across the application.
    """
    
    _instance: Optional['ClipboardManager'] = None
    
    def __new__(cls, project: Optional['Project'] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, project: Optional['Project'] = None):
        if self._initialized:
            return
        
        self.service = ClipboardService(project)
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'ClipboardManager':
        """Get the singleton ClipboardManager instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_project(self, project: 'Project') -> None:
        """Set the project for the clipboard service."""
        self.service.project = project

    def set_clipboard_widget(self, widget) -> None:
        """
        Give the clipboard a way to reach the desktop's.

        PARAMETERS:
        -----------
        widget : tk.Misc
            Any widget of the application's; only its clipboard methods are
            used. Without one, copying still works within this window.
        """
        self.service.clipboard_widget = widget

    @property
    def cut_item_ids(self):
        """The rows marked as cut and awaiting a paste."""
        return self.service.cut_item_ids


    def copy(self, selected_ids: Optional[List[str]] = None) -> None:
        """Copy selected items to clipboard."""
        self.service.copy(selected_ids)
    
    def cut(self, selected_ids: Optional[List[str]] = None) -> None:
        """Cut selected items to clipboard."""
        self.service.cut(selected_ids)
    
    def paste(self, target_container_id: Optional[str] = None,
              insert_index: Optional[int] = None) -> List[str]:
        """Paste from the clipboard, and say which rows arrived."""
        return self.service.paste(target_container_id, insert_index)
    
    def clear(self) -> None:
        """Clear the clipboard."""
        self.service.clear_clipboard()
    
    def is_empty(self) -> bool:
        """Check if clipboard is empty."""
        return self.service.is_clipboard_empty()
    
    def can_paste(self, target_container_id: Optional[str] = None) -> bool:
        """Check if paste is possible for target container."""
        return self.service.can_paste(target_container_id)
    
    def can_copy_or_cut(self, selected_ids: Optional[List[str]] = None) -> bool:
        """Check if copy or cut is possible."""
        return self.service.can_copy_or_cut(selected_ids)


def setup_keyboard_bindings(root: Any, clipboard_manager: ClipboardManager, 
                            get_selected_ids: callable, 
                            get_target_container: callable,
                            on_clipboard_change: callable = None) -> None:
    """
    Set up keyboard shortcut bindings for copy, cut, and paste.
    
    Args:
        root: The root Tk window
        clipboard_manager: The ClipboardManager instance
        get_selected_ids: Function that returns the currently selected task IDs
        get_target_container: Function that returns the target container ID for paste
        on_clipboard_change: Optional callback when clipboard state changes
    """
    def handle_key_press(event: Any) -> None:
        """Handle keyboard shortcuts."""
        import tkinter as tk
        focused = root.focus_get()
        if focused and hasattr(focused, 'winfo_class'):
            widget_class = focused.winfo_class()
            if widget_class in ('Entry', 'Text', 'Spinbox', 'TEntry'):
                return
        
        ctrl_pressed = (event.state & 0x4) != 0
        cmd_pressed = (event.state & 0x8) != 0
        
        if not (ctrl_pressed or cmd_pressed):
            return
        
        key = event.keysym.lower()
        
        if key == 'c':
            selected_ids = get_selected_ids()
            if clipboard_manager.can_copy_or_cut(selected_ids):
                clipboard_manager.copy(selected_ids)
                if on_clipboard_change:
                    on_clipboard_change()
        
        elif key == 'x':
            selected_ids = get_selected_ids()
            if clipboard_manager.can_copy_or_cut(selected_ids):
                clipboard_manager.cut(selected_ids)
                if on_clipboard_change:
                    on_clipboard_change()
        
        elif key == 'v':
            target_container_id = get_target_container()
            if clipboard_manager.can_paste(target_container_id):
                clipboard_manager.paste(target_container_id)
                if on_clipboard_change:
                    on_clipboard_change()
    
    root.bind('<Control-Key-c>', handle_key_press, add='+')
    root.bind('<Control-Key-x>', handle_key_press, add='+')
    root.bind('<Control-Key-v>', handle_key_press, add='+')
    root.bind('<Command-Key-c>', handle_key_press, add='+')
    root.bind('<Command-Key-x>', handle_key_press, add='+')
    root.bind('<Command-Key-v>', handle_key_press, add='+')

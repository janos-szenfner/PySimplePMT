"""
Toolbar for the Gantt Project Management Tool.

Contains action buttons for managing the project.
"""

import tkinter as tk
from tkinter import simpledialog
# Message boxes and file choosers that stay native on every desktop:
# Tk's own are native on macOS and Windows but drawn by Tk on X11.
# Aliased so the call sites below read exactly as they always have.
from gantt_app.views import dialogs as messagebox
from gantt_app.views import dialogs as filedialog
from typing import Optional, Callable, List, Dict

import customtkinter as ctk

from gantt_app.models import Task, Project
from gantt_app.utils.file_io import save_project, load_project
from gantt_app.utils.gan_importer import import_gan_file
from gantt_app.utils.mpp_importer import import_mpp_file
from gantt_app.utils.mermaid_importer import import_mermaid_file
from gantt_app.utils.xlsx_importer import import_xlsx_file
from gantt_app.utils.mermaid_exporter import export_project_to_mermaid
from gantt_app.utils.xlsx_exporter import export_project_to_xlsx
from gantt_app.utils.undoredo import UndoRedoManager
from gantt_app.views.modal import grab_when_visible
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)

#: Toolbar palette. A single standard blue with white text, rather than the
#: pure #0000FF buttons and dark green menu rows used previously - saturated
#: primaries read as unfinished and gave poor contrast against the dark menu
#: background.
ACCENT = "#1f6aa5"          # buttons and menu rows
ACCENT_HOVER = "#17537f"    # hover / pressed
ACCENT_TEXT = "#ffffff"
MENU_BG = "#1f2937"         # menu panel behind the rows
MENU_BORDER = "#3b4759"
LOG_ACCENT = "#b8860b"      # the Log button stays distinct
LOG_ACCENT_HOVER = "#966d09"

# Windows-style menu bar colors
WIN_MENU_BG = "#F1F3F5"     # light gray background for menu bar
WIN_MENU_HOVER = "#E9ECEF"  # hover color for menu items
WIN_MENU_TEXT = "#1C1D1F"   # dark text color
WIN_DROPDOWN_BG = "#F8F9FA" # light background for dropdown menus


class CTkDropdownMenu(ctk.CTkToplevel):
    """Floating dropdown menu window for CustomTkinter with Windows-style appearance."""
    
    ITEM_HEIGHT = 28
    MENU_PADDING = 4
    
    def __init__(self, master, items: List[Dict], **kwargs):
        super().__init__(master, **kwargs)
        
        # Window setup for floating overlay
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=WIN_DROPDOWN_BG, corner_radius=8)
        
        self.items = items
        self._create_widgets()
        
        # Bind global click to dismiss menu when clicking outside
        self.bind("<FocusOut>", lambda e: self._on_focus_out())
        self.bind("<Escape>", lambda e: self.destroy())
        
        # Track if we're in a submenu operation to prevent premature closing
        self._in_submenu = False
        
    def _create_widgets(self):
        container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=8)
        container.pack(fill="both", expand=True, padx=self.MENU_PADDING, pady=self.MENU_PADDING)

        for item in self.items:
            self._create_menu_item(container, item)
            
    def _create_menu_item(self, container, item: Dict):
        """Create a single menu item based on its type."""
        # Determine item type - check if it has submenu/items first
        if item.get("type") == "separator":
            item_type = "separator"
        elif "submenu" in item or "items" in item:
            item_type = "submenu"
        elif item.get("type") == "toggle":
            item_type = "toggle"
        else:
            item_type = "action"
            
        label_text = item.get("label", item.get("text", ""))
        
        # Row container
        row = ctk.CTkFrame(container, fg_color="transparent", corner_radius=6, height=self.ITEM_HEIGHT)
        row.pack(fill="x", pady=1)

        if item_type == "separator":
            # Create a separator line
            separator = ctk.CTkFrame(row, height=1, fg_color="#6C757D", corner_radius=0)
            separator.pack(fill="x", pady=4)
            return

        if item_type == "toggle":
            var = item.get("variable")
            check_str = "✓" if (var and var.get()) else " "
            
            # Create handler to avoid lambda scoping issues
            def make_toggle_handler(i, v):
                return lambda: self._handle_toggle(i, v)
            
            btn = ctk.CTkButton(
                row,
                text=f"{check_str}  {label_text}",
                anchor="w",
                fg_color="transparent",
                text_color=WIN_MENU_TEXT,
                hover_color=WIN_MENU_HOVER,
                height=self.ITEM_HEIGHT - 2,
                corner_radius=6,
                command=make_toggle_handler(item, var)
            )
            btn.pack(fill="x", expand=True)

        elif item_type == "action":
            # Create handler to avoid lambda scoping issues
            def make_action_handler(i):
                return lambda: self._handle_action(i)
            
            btn = ctk.CTkButton(
                row,
                text=f"    {label_text}",
                anchor="w",
                fg_color="transparent",
                text_color=WIN_MENU_TEXT,
                hover_color=WIN_MENU_HOVER,
                height=self.ITEM_HEIGHT - 2,
                corner_radius=6,
                command=make_action_handler(item)
            )
            btn.pack(fill="x", expand=True)

        elif item_type == "submenu":
            submenu_items = item.get("submenu", item.get("items", []))
            
            # Create handler to avoid lambda scoping issues
            def make_submenu_handler(i, s, r):
                return lambda: self._handle_submenu(i, s, r)
            
            btn = ctk.CTkButton(
                row,
                text=f"    {label_text}",
                anchor="w",
                fg_color="transparent",
                text_color=WIN_MENU_TEXT,
                hover_color=WIN_MENU_HOVER,
                height=self.ITEM_HEIGHT - 2,
                corner_radius=6,
                command=make_submenu_handler(item, submenu_items, row)
            )
            btn.pack(side="left", fill="x", expand=True)
            
            arrow = ctk.CTkLabel(row, text=">", text_color="#6C757D", width=20)
            arrow.pack(side="right", padx=5)
            
            # Store submenu reference for hover support
            btn.submenu_items = submenu_items
            btn.row_frame = row
            
            # Bind hover events for submenu - use a wrapper to avoid scoping issues
            def make_hover_handler(s_items, r, b):
                return lambda e: self._on_submenu_hover(s_items, r, b)
            
            btn.bind("<Enter>", make_hover_handler(submenu_items, row, btn))
            row.bind("<Enter>", make_hover_handler(submenu_items, row, btn))

    def _handle_toggle(self, item: Dict, var: Optional[ctk.BooleanVar]):
        if var is not None:
            var.set(not var.get())
        if "command" in item and callable(item["command"]):
            try:
                item["command"](var.get() if var else None)
            except Exception:
                logger.exception("Menu action failed")
                messagebox.showerror(
                    "Action Failed",
                    "That action could not be completed. "
                    "See the Log window for details."
                )
        self._close_all_menus()

    def _handle_action(self, item: Dict):
        if "command" in item and callable(item["command"]):
            try:
                item["command"]()
            except Exception:
                logger.exception("Menu action failed")
                messagebox.showerror(
                    "Action Failed",
                    "That action could not be completed. "
                    "See the Log window for details."
                )
        self._close_all_menus()

    def _handle_submenu(self, item: Dict, submenu_items: List[Dict], row):
        # Close any existing submenu first
        self._close_all_menus()
        
        if not submenu_items:
            return
            
        # Calculate position to the right of the current menu
        x = self.winfo_rootx() + self.winfo_width() - 4
        y = self.winfo_rooty() + row.winfo_rooty() - self.winfo_rooty()
        
        self._in_submenu = True
        submenu = CTkDropdownMenu(self, items=submenu_items)
        submenu.geometry(f"+{x}+{y}")
        submenu.focus_set()
        self._in_submenu = False

    def _on_submenu_hover(self, submenu_items: List[Dict], row, button):
        """Handle hover to open submenu after a short delay."""
        if not submenu_items:
            return
            
        # Close any existing submenus
        for child in self.winfo_children():
            if isinstance(child, CTkDropdownMenu) and child != self:
                try:
                    child.destroy()
                except:
                    pass
                    
        # Calculate position to the right of the current menu
        x = self.winfo_rootx() + self.winfo_width() - 4
        y = self.winfo_rooty() + row.winfo_rooty() - self.winfo_rooty()
        
        self._in_submenu = True
        submenu = CTkDropdownMenu(self, items=submenu_items)
        submenu.geometry(f"+{x}+{y}")
        submenu.focus_set()
        self._in_submenu = False

    def _on_focus_out(self):
        """Handle focus out to close the menu."""
        if self._in_submenu:
            return
        self._close_all_menus()

    def _close_all_menus(self):
        """Close this menu and any submenus."""
        try:
            self.destroy()
        except tk.TclError:
            pass


class CustomMenuBar(ctk.CTkFrame):
    """Horizontal navigation bar holding root menu triggers with Windows-style appearance."""
    
    def __init__(self, master, menu_config: Dict[str, List[Dict]], **kwargs):
        super().__init__(master, height=35, corner_radius=0, fg_color=WIN_MENU_BG, **kwargs)
        self.menu_config = menu_config
        self.active_dropdown: Optional[CTkDropdownMenu] = None
        self._dismiss_binding = None
        
        # Store references to all menu buttons for state management
        self.menu_buttons = []
        self._build_bar()
        
    def _build_bar(self):
        for title, items in self.menu_config.items():
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(side="left", padx=2, pady=4)
            
            # Create a bound method for this specific button and items
            def create_handler(btn_title, menu_items):
                def handler():
                    # Find the button by title
                    for btn in self.menu_buttons:
                        if btn.cget("text") == btn_title:
                            self._show_dropdown(btn, menu_items)
                            break
                return handler
            
            btn = ctk.CTkButton(
                btn_frame,
                text=title,
                width=60,
                height=26,
                fg_color="transparent",
                text_color=WIN_MENU_TEXT,
                hover_color=WIN_MENU_HOVER,
                corner_radius=6,
                command=create_handler(title, items)
            )
            btn.pack(side="left", padx=5, pady=5)
            self.menu_buttons.append(btn)
            
    def _show_dropdown(self, button_widget: ctk.CTkButton, items: List[Dict]):
        # Close any existing dropdown
        self._close_all_dropdowns()
        
        # Calculate position directly below root button
        x = button_widget.winfo_rootx()
        y = button_widget.winfo_rooty() + button_widget.winfo_height() + 2
        
        self.active_dropdown = CTkDropdownMenu(self, items=items)
        self.active_dropdown.geometry(f"+{x}+{y}")
        self.active_dropdown.focus_set()
        
        # Store reference to the button that opened this menu
        self.active_dropdown.opener_button = button_widget
        
        # Bind global click to dismiss menu when clicking outside
        self._dismiss_binding = self.winfo_toplevel().bind(
            "<Button-1>", self._on_click_elsewhere, add="+"
        )
        
    def _on_click_elsewhere(self, event):
        """Close the menu when the click lands outside it."""
        if not self.active_dropdown or not self.active_dropdown.winfo_exists():
            return
        
        # Check if click is inside the menu or the opener button
        if event.widget is self:
            return
            
        # Try to find if the click is inside any menu or menu button
        widget = event.widget
        is_inside_menu = False
        
        # Check if widget is inside the active dropdown
        try:
            menu_window = self.active_dropdown
            if widget.winfo_containing(menu_window.winfo_id()):
                is_inside_menu = True
        except:
            pass
            
        # Check if widget is one of our menu buttons
        if hasattr(self, 'menu_buttons'):
            for btn in self.menu_buttons:
                if widget is btn or widget.winfo_containing(btn.winfo_id()):
                    is_inside_menu = True
                    break
                    
        if not is_inside_menu:
            self._close_all_dropdowns()

    def _close_all_dropdowns(self):
        """Close all open dropdown menus."""
        # Clean up the dismiss binding
        if hasattr(self, '_dismiss_binding') and self._dismiss_binding:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._dismiss_binding)
            except tk.TclError:
                pass
            self._dismiss_binding = None
            
        if self.active_dropdown and self.active_dropdown.winfo_exists():
            try:
                self.active_dropdown.destroy()
            except tk.TclError:
                pass
        self.active_dropdown = None
        
        # Reset button states
        for btn in self.menu_buttons:
            btn.configure(fg_color="transparent")


class DropdownButton(ctk.CTkButton):
    """Custom dropdown button that shows a menu when clicked."""
    
    def __init__(self, master, text: str, menu_items: List[Dict], 
                 width: int = 100, fg_color: str = None, hover_color: str = None,
                 **kwargs):
        """
        Create a dropdown button.
        
        PARAMETERS:
        -----------
        master : widget
            Parent widget
        text : str
            Button text
        menu_items : List[Dict]
            List of menu item dictionaries with 'text' and 'command' keys
        width : int
            Button width
        fg_color : str
            Button foreground color
        hover_color : str
            Button hover color
        **kwargs : dict
            Additional keyword arguments for CTkButton
        """
        # Set the command before calling super().__init__
        kwargs['command'] = self._show_menu
        
        super().__init__(master, text=text, width=width, 
                        fg_color=fg_color, hover_color=hover_color, **kwargs)
        
        self.menu_items = menu_items
        self._popups = []
        self._dismiss_binding = None
    
    #: The dropdown currently showing its menu, if any. Only one opens at a
    #: time, so clicking a second button dismisses the first.
    _open_menu_owner = None

    ITEM_HEIGHT = 34
    MENU_WIDTH = 220
    MENU_PADDING = 8

    def _show_menu(self):
        """
        Show the dropdown menu, or close it if it is already open.

        DEVELOPMENT NOTES:
        ------------------
        The whole build runs inside a try/except that tears the popup down on
        failure. An earlier version passed an unsupported argument to
        CTkButton; the exception escaped part-way through, leaving an empty,
        undecorated, always-on-top window with no bindings and no way to
        dismiss it. Every click on a menu button added another one.
        """
        if self._popups:
            self.close_menu()
            return

        DropdownButton.close_open_menu()

        try:
            DropdownButton._open_menu_owner = self
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            self._open_popup(self.menu_items, x, y, level=0)

            toplevel = self.winfo_toplevel()
            self._dismiss_binding = toplevel.bind(
                "<Button-1>", self._on_click_elsewhere, add="+"
            )
        except Exception:
            logger.exception("Could not build the %r menu", self.cget("text"))
            self.close_menu()

    def _open_popup(self, items, x, y, level):
        """
        Open one level of the menu at the given screen position.

        PARAMETERS:
        -----------
        items : List[Dict]
            Entries for this level. An entry with a 'submenu' key opens a
            further level instead of running a command.
        x, y : int
            Screen coordinates for the top left of the popup.
        level : int
            Nesting depth; 0 is the menu directly under the button.

        DEVELOPMENT NOTES:
        ------------------
        Opening a level closes anything already open at that depth or below,
        which is what lets the pointer move between sibling submenus without
        leaving orphaned popups behind.
        """
        self._close_from_level(level)

        popup = ctk.CTkToplevel(self.master)
        popup.title("")
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)

        height = len(items) * self.ITEM_HEIGHT + self.MENU_PADDING * 2
        popup.geometry(f"{self.MENU_WIDTH}x{height}+{x}+{y}")

        frame = ctk.CTkFrame(popup, fg_color=MENU_BG, corner_radius=0,
                             border_width=1, border_color=MENU_BORDER)
        frame.pack(fill=tk.BOTH, expand=True)

        for index, item in enumerate(items):
            submenu = item.get('submenu')
            label = item['text'] + ('   >' if submenu else '')

            if submenu:
                command = (lambda entries=submenu, row=index, lvl=level:
                           self._open_submenu(entries, row, lvl))
            else:
                command = (lambda cmd=item.get('command'):
                           self._on_menu_select(cmd))

            button = ctk.CTkButton(
                frame, text=label, command=command,
                height=self.ITEM_HEIGHT - 4,
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                text_color=ACCENT_TEXT, anchor="w", corner_radius=0
            )
            button.pack(fill=tk.X, padx=self.MENU_PADDING, pady=2)

        popup.bind("<Escape>", lambda _e: self.close_menu())
        self._popups.append(popup)
        popup.focus_set()
        return popup

    def _open_submenu(self, items, row, level):
        """Open a child menu beside the row that owns it."""
        parent = self._popups[level]
        x = parent.winfo_rootx() + self.MENU_WIDTH - 4
        y = parent.winfo_rooty() + self.MENU_PADDING + row * self.ITEM_HEIGHT
        self._open_popup(items, x, y, level + 1)

    def _close_from_level(self, level):
        """Destroy every popup at or below a nesting depth."""
        while len(self._popups) > level:
            popup = self._popups.pop()
            try:
                popup.destroy()
            except tk.TclError:
                pass

    def _menu_is_alive(self) -> bool:
        """Check whether any part of the menu is still open."""
        return bool(self._popups)

    def _on_click_elsewhere(self, event):
        """Close the menu when the click lands outside it."""
        if not self._popups:
            return
        if event.widget is self:
            # Handled by the toggle in _show_menu
            return
        self.close_menu()

    def close_menu(self):
        """
        Dismiss every level of the menu and release its bindings.

        DEVELOPMENT NOTES:
        ------------------
        Safe to call when no menu is open, and never raises: it runs from
        window teardown, where a half-destroyed widget tree is normal.
        """
        binding = getattr(self, '_dismiss_binding', None)
        if binding is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", binding)
            except tk.TclError:
                pass
            self._dismiss_binding = None

        self._close_from_level(0)

        if DropdownButton._open_menu_owner is self:
            DropdownButton._open_menu_owner = None

    @classmethod
    def close_open_menu(cls):
        """Close whichever dropdown is currently showing a menu."""
        owner = cls._open_menu_owner
        if owner is not None:
            owner.close_menu()

    def _on_menu_select(self, command):
        """Handle menu item selection."""
        self.close_menu()

        if command:
            try:
                command()
            except Exception:
                logger.exception("Menu action failed")
                messagebox.showerror(
                    "Action Failed",
                    "That action could not be completed. "
                    "See the Log window for details."
                )


class Toolbar(ctk.CTkFrame):
    """
    Toolbar with action buttons for the Gantt application.
    """
    
    def __init__(self, master, project: Project,
                 on_project_changed: Callable[[], None] = None,
                 gantt_chart=None,
                 undo_redo_manager: UndoRedoManager = None,
                 clipboard_manager=None):
        super().__init__(master)
        
        self.master = master
        self.project = project
        self.on_project_changed = on_project_changed
        self.gantt_chart = gantt_chart
        self.undo_redo_manager = undo_redo_manager
        self.clipboard_manager = clipboard_manager
        
        # Create UI
        self._create_ui()
    
    def _create_ui(self):
        """
        Create the toolbar user interface.

        DEVELOPMENT NOTES:
        ------------------
        The menus are declared in one place, in the order they appear, so the
        arrangement can be read at a glance instead of being spread across a
        builder per menu. An entry with a 'submenu' opens a nested level.
        """
        # Convert existing menu definitions to new format
        menu_config = self._convert_to_new_menu_format()
        
        # Create graphical icon toolbar
        self.icon_toolbar = IconToolbar(
            self, self.project,
            on_project_changed=self.on_project_changed,
            undo_redo_manager=self.undo_redo_manager,
            clipboard_manager=self.clipboard_manager
        )
        self.icon_toolbar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Connect icon toolbar actions to toolbar methods
        self._connect_icon_toolbar()
        
        # Create Windows-style menu bar (keep for dropdown menus)
        self.menu_bar = CustomMenuBar(self, menu_config=menu_config)
        self.menu_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Theme toggle and Log buttons
        self._create_theme_log_buttons()
    
    def _connect_icon_toolbar(self):
        """Connect the icon toolbar button actions to the toolbar's methods."""
        if not hasattr(self, 'icon_toolbar'):
            return
        
        # Override the icon toolbar's methods with the toolbar's methods
        self.icon_toolbar.new_project = self.new_project
        self.icon_toolbar.load_project = self.load_project
        self.icon_toolbar.save_project = self.save_project
        self.icon_toolbar.edit_project_info = self.edit_project_info
        self.icon_toolbar.add_task = self.add_task
        self.icon_toolbar.add_subtask = self.add_subtask
        self.icon_toolbar.add_milestone = self.add_milestone
        self.icon_toolbar.cut_tasks = self.cut_tasks
        self.icon_toolbar.copy_tasks = self.copy_tasks
        self.icon_toolbar.paste_tasks = self.paste_tasks
        self.icon_toolbar.delete_selected = lambda: self._delete_selected_tasks()
        self.icon_toolbar.undo = self.undo
        self.icon_toolbar.redo = self.redo
    
    def _delete_selected_tasks(self):
        """Delete selected tasks from the task list."""
        if hasattr(self.task_list, 'get_selected_task_ids'):
            selected_ids = self.task_list.get_selected_task_ids()
            if selected_ids and self.project:
                if messagebox.askyesno("Delete", f"Delete {len(selected_ids)} selected task(s)?"):
                    for task_id in selected_ids:
                        self.project.remove_task(task_id)
                    if self.on_project_changed:
                        self.on_project_changed()

    def _convert_to_new_menu_format(self):
        """
        Convert the existing menu definitions to the new Windows-style format.
        
        RETURNS:
        --------
        Dict[str, List[Dict]]
            Menu configuration for CustomMenuBar with 'label', 'type', etc.
        """
        config = {}
        
        for definition in self._menu_definitions():
            menu_name = definition['text']
            config[menu_name] = self._convert_items_to_new_format(definition['items'])
        
        return config
        
    def _convert_items_to_new_format(self, items):
        """
        Convert a list of menu items from old format to new format.
        
        PARAMETERS:
        -----------
        items : List[Dict]
            List of menu items in old format
            
        RETURNS:
        --------
        List[Dict]
            List of menu items in new format
        """
        new_items = []
        
        for item in items:
            # Skip separator items in the old format - they're handled differently
            if item.get('type') == 'separator':
                continue
                
            new_item = {}
            
            if 'submenu' in item:
                # This is a submenu item
                new_item['label'] = item['text']
                new_item['type'] = 'submenu'
                new_item['items'] = self._convert_items_to_new_format(item['submenu'])
            elif 'command' in item:
                # This is an action item
                new_item['label'] = item['text']
                new_item['type'] = 'action'
                new_item['command'] = item['command']
            else:
                # Fallback - treat as action
                new_item['label'] = item.get('text', item.get('label', ''))
                new_item['type'] = 'action'
                new_item['command'] = item.get('command')
                
            new_items.append(new_item)
            
        return new_items

    def _menu_definitions(self):
        """
        Describe every toolbar menu, left to right.

        RETURNS:
        --------
        List[Dict]
            One entry per top-level menu, each with its text and items.
        """
        return [
            {
                'text': 'Project',
                'items': [
                    {"text": "New Project...", "command": self.new_project},
                    {"text": "Load Project...", "command": self.load_project},
                    {"text": "Save Project...", "command": self.save_project},
                ],
            },
            {
                'text': 'File',
                'items': [
                    {"text": "Import", "submenu": [
                        {"text": "MPP...", "command": self.import_mpp},
                        {"text": "GAN...", "command": self.import_gan},
                        {"text": "Mermaid...", "command": self.import_mermaid},
                        {"text": "XLSX...", "command": self.import_xlsx},
                    ]},
                    {"text": "Export", "submenu": [
                        {"text": "Mermaid...", "command": self.export_mermaid},
                        {"text": "HTML...", "command": self.export_html},
                        {"text": "SVG...", "command": self.export_svg},
                        {"text": "PNG...", "command": self.export_png},
                        {"text": "PDF...", "command": self.export_pdf},
                        {"text": "XLSX...", "command": self.export_xlsx},
                    ]},
                ],
            },
            {
                'text': 'Actions',
                'items': [
                    {"text": "Create", "submenu": [
                        {"text": "Phase...", "command": self.add_phase},
                        {"text": "Deliverable...", "command": self.add_deliverable},
                        {"text": "Task...", "command": self.add_task},
                        {"text": "Subtask...", "command": self.add_subtask},
                        {"text": "Milestone...", "command": self.add_milestone},
                    ]},
                    # Renaming the project is not a create action, so it sits
                    # beside Create rather than inside it
                    {"text": "Project Title...", "command": self.edit_project_info},
                ],
            },
            {
                'text': 'Edit',
                'items': [
                    {"text": "Undo", "command": self.undo},
                    {"text": "Redo", "command": self.redo},
                    {"text": "Cut", "command": self.cut_tasks},
                    {"text": "Copy", "command": self.copy_tasks},
                    {"text": "Paste", "command": self.paste_tasks},
                ],
            },
            {
                'text': 'View',
                'items': [
                    {"text": "Toggle Theme", "command": self.toggle_theme},
                    {"text": "Gantt Chart Settings", "command": self.open_gantt_chart_settings},
                ],
            },
        ]

    def _add_menu(self, text, items):
        """Add one top-level menu button to the toolbar."""
        frame = ctk.CTkFrame(self)
        frame.pack(side=tk.LEFT, padx=5, pady=5)

        button = DropdownButton(
            frame,
            text=text,
            menu_items=items,
            width=100,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT
        )
        button.pack(side=tk.LEFT, padx=5, pady=5)
        return button

    def _create_theme_log_buttons(self):
        """Create the log button."""
        theme_frame = ctk.CTkFrame(self)
        theme_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        # Log viewer
        self.log_button = ctk.CTkButton(
            theme_frame, text="Log",
            command=self.show_log, width=70,
            fg_color=LOG_ACCENT,
            hover_color=LOG_ACCENT_HOVER,
            text_color="white"
        )
        self.log_button.pack(side=tk.LEFT, padx=5, pady=5)

    def show_log(self):
        """Open the application log window."""
        try:
            from gantt_app.views.log_window import LogWindow
            LogWindow.show(self.winfo_toplevel())
            logger.debug("Log window opened")
        except Exception as e:
            logger.exception("Could not open the log window")
            messagebox.showerror(
                "Log Unavailable",
                f"Could not open the log window:\n{e}"
            )

    def _create_of_type(self, task_type: str):
        """
        Open the create dialog for one kind of work item.

        PARAMETERS:
        -----------
        task_type : str
            One of models.TASK_TYPES.
        """
        from gantt_app.views.taskdialogs import CreateTaskDialog

        dialog = CreateTaskDialog(
            self.master, self.project,
            task_type=task_type,
            on_save=self._save_new_task
        )
        dialog.wait_window()

    def add_phase(self):
        """Add a phase: the outermost grouping, bracketing deliverables."""
        self._create_of_type("Phase")

    def add_deliverable(self):
        """Add a deliverable: a grouping of the tasks that produce it."""
        self._create_of_type("Deliverable")

    def add_task(self):
        """Add a new task to the project with undo support."""
        self._create_of_type("Task")


    def _save_new_task(self, task: Task):
        """Handle saving a newly created task with undo support."""
        # Use undo/redo if available
        if self.undo_redo_manager:
            from gantt_app.utils.undoredo import create_add_task_command
            command = create_add_task_command(self.project, task)
            logger.info("Created %s %s %r starting %s",
                        "milestone" if task.is_milestone else task.task_type.lower(),
                        task.id, task.name, task.start_date.date())
            if self.undo_redo_manager.execute(command):
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
        else:
            # Fallback to direct addition
            self.project.add_task(task)
            if self.on_project_changed:
                self.on_project_changed()
    
    def add_milestone(self):
        """Add a new milestone to the project with undo support."""
        self._create_of_type("Milestone")
    
    def add_subtask(self):
        """Add a new subtask to the project with undo support."""
        from gantt_app.models import Task
        from gantt_app.views.taskdialogs import CreateTaskDialog
        
        # Any task can be a parent, including an existing sub-task, so that
        # hierarchies deeper than two levels can be built
        candidate_parents = self._candidate_parent_tasks()
        if not candidate_parents:
            messagebox.showwarning("No Parent Task", "You need at least one task to create a subtask.")
            return
        
        # If only one parent, use it directly
        if len(candidate_parents) == 1:
            parent_task = candidate_parents[0]
            dialog = CreateTaskDialog(
                self.master, self.project,
                task_type="Subtask",
                parent_task=parent_task,
                on_save=self._save_new_task
            )
            dialog.wait_window()
        else:
            # Let user select parent first, then open full dialog
            parent_task = self._select_parent_task(candidate_parents)
            if parent_task:
                dialog = CreateTaskDialog(
                    self.master, self.project,
                    task_type="Subtask",
                    parent_task=parent_task,
                    on_save=self._save_new_task
                )
                dialog.wait_window()
    
    def _candidate_parent_tasks(self) -> List[Task]:
        """
        Get the tasks that may act as a parent, in hierarchy order.

        RETURNS:
        --------
        List[Task]
            Every non-milestone task, each parent immediately followed by its
            own descendants, so the selection list reads as a tree.

        DEVELOPMENT NOTES:
        ------------------
        Sub-tasks are included, which is what allows hierarchies deeper than
        two levels to be built from the UI. Imported files (GanttProject in
        particular) already nest several levels deep, so restricting this to
        root tasks made the UI unable to express what the importers produce.
        Milestones are excluded because they are single-date markers with no
        span for a child to sit inside.
        """
        by_parent = {}
        for task in self.project.tasks:
            by_parent.setdefault(task.parent_task_id, []).append(task)

        for group in by_parent.values():
            group.sort(key=lambda t: t.start_date)

        ordered: List[Task] = []
        visited = set()

        def walk(parent_id):
            for task in by_parent.get(parent_id, []):
                if task.id in visited:
                    continue
                visited.add(task.id)
                if not task.effective_milestone and task.can_have_children:
                    ordered.append(task)
                walk(task.id)

        walk(None)

        # Include anything unreachable from the root (orphaned parent reference)
        for task in self.project.tasks:
            if task.id not in visited and not task.effective_milestone and task.can_have_children:
                ordered.append(task)

        return ordered

    def _task_depth(self, task: Task) -> int:
        """Get how many levels down a task sits, 0 for a root task."""
        depth = 0
        current = task
        seen = {current.id}
        while current.parent_task_id:
            parent = self.project.get_task_by_id(current.parent_task_id)
            if parent is None or parent.id in seen:
                break
            seen.add(parent.id)
            current = parent
            depth += 1
        return depth

    def _select_parent_task(self, candidate_tasks: List[Task]) -> Optional[Task]:
        """
        Show a dialog to select a parent task for a subtask.

        PARAMETERS:
        -----------
        candidate_tasks : List[Task]
            Tasks that can be parents, in hierarchy order

        RETURNS:
        --------
        Optional[Task]
            The selected parent task, or None if cancelled

        DEVELOPMENT NOTES:
        ------------------
        Uses a dictionary to map listbox indices to task objects.
        This provides a clean way to retrieve the selected task.
        Entries are indented by depth so nesting is visible when picking a
        sub-task as the parent.
        """
        # Create a simple dialog with a listbox
        dialog = tk.Toplevel(self.master)
        dialog.title("Select Parent Task")
        dialog.geometry("400x300")
        dialog.transient(self.master)
        # Deferred: grabbing before the window is mapped fails on X11
        grab_when_visible(dialog)
        
        # Add label
        label = tk.Label(dialog, text="Select a parent task for the subtask:")
        label.pack(pady=10)
        
        # Create listbox
        listbox = tk.Listbox(dialog, width=50, height=10)
        listbox.pack(padx=20, pady=10)
        
        # Store mapping from index to task
        task_map = {}
        
        # Add tasks to listbox, indented by how deep they sit
        for i, task in enumerate(candidate_tasks):
            indent = "    " * self._task_depth(task)
            display_name = f"{indent}{task.name} ({task.start_date.strftime('%Y-%m-%d')})"
            listbox.insert(tk.END, display_name)
            task_map[i] = task
        
        # Add buttons
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        
        selected_task = [None]  # Use list to allow modification in nested function
        
        def on_ok():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                selected_task[0] = task_map.get(idx)
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        ok_btn = tk.Button(button_frame, text="OK", command=on_ok)
        ok_btn.pack(side=tk.LEFT, padx=10)
        
        cancel_btn = tk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_btn.pack(side=tk.LEFT, padx=10)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        return selected_task[0]
    
    def edit_project_info(self):
        """Edit the project title with undo support."""
        new_name = simpledialog.askstring(
            "Project Title", "Enter the project title:",
            parent=self.master, initialvalue=self.project.name
        )
        
        if new_name and new_name != self.project.name:
            if self.undo_redo_manager:
                from gantt_app.utils.undoredo import create_update_project_name_command
                command = create_update_project_name_command(self.project, self.project.name, new_name)
                if self.undo_redo_manager.execute(command):
                    self.update_undo_redo_buttons()
                    if self.on_project_changed:
                        self.on_project_changed()
            else:
                # Fallback to direct update
                self.project.name = new_name
                if self.on_project_changed:
                    self.on_project_changed()
    
    def save_project(self):
        """Save the current project to a JSON file."""
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save Project"
        )
        
        if not file_path:
            return
        
        # Save project
        logger.info("Saving project %r to %s", self.project.name, file_path)
        if save_project(self.project, file_path):
            messagebox.showinfo("Success", "Project saved successfully!")
        else:
            messagebox.showerror("Error", "Failed to save project")
    
    def load_project(self):
        """Load a project from a JSON file."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Load Project"
        )
        
        if not file_path:
            return
        
        # Load project
        logger.info("Loading project from %s", file_path)
        project = load_project(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date
            
            # Clear undo/redo history when loading a new project
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
        else:
            messagebox.showerror("Error", "Failed to load project")
    
    def new_project(self):
        """Create a new empty project."""
        new_name = tk.simpledialog.askstring(
            "New Project", "Enter project name:", 
            parent=self.master, initialvalue="New Project"
        )
        
        if new_name:
            # Clear current project
            self.project.name = new_name
            self.project.tasks = []
            self.project.start_date = None
            self.project.end_date = None
            
            # Clear undo/redo history for new project
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
    
    def import_gan(self):
        """Import a GanttProject (.gan) file."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("GanttProject Files", "*.gan"), ("All Files", "*.*")],
            title="Import GAN File"
        )
        
        if not file_path:
            return
        
        # Import GAN file
        project = import_gan_file(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date
            
            # Clear undo/redo history when importing
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
            
            messagebox.showinfo("Success", f"Imported {len(project.tasks)} tasks from GAN file")
        else:
            messagebox.showerror("Error", "Failed to import GAN file")
    
    def import_mpp(self):
        """Import a Microsoft Project (.mpp) file."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("Microsoft Project Files", "*.mpp"), ("All Files", "*.*")],
            title="Import MPP File"
        )
        
        if not file_path:
            return
        
        # Import MPP file
        project = import_mpp_file(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date
            
            # Clear undo/redo history when importing
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
            
            tk.messagebox.showinfo("Success", f"Imported {len(project.tasks)} tasks from MPP file")
        else:
            messagebox.showerror(
                "Error",
                "Failed to import MPP file.\n\n"
                "MS Project import needs the optional Tasklib reader:\n"
                "    pip install tasklib"
            )
    
    def import_mermaid(self):
        """Import a Mermaid (.mmd or .mermaid) file."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("Mermaid Files", "*.mmd;*.mermaid"), ("All Files", "*.*")],
            title="Import Mermaid File"
        )
        
        if not file_path:
            return
        
        # Import Mermaid file
        project = import_mermaid_file(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date
            
            # Clear undo/redo history when importing
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()
            
            if self.on_project_changed:
                self.on_project_changed()
            
            messagebox.showinfo("Success", f"Imported {len(project.tasks)} tasks from Mermaid file")
        else:
            messagebox.showerror("Error", "Failed to import Mermaid file")
    
    def import_xlsx(self):
        """Import an Excel (.xlsx) project plan."""
        # Ask for file path
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel Files", "*.xlsx;*.xlsm"), ("All Files", "*.*")],
            title="Import XLSX File"
        )

        if not file_path:
            return

        # Import XLSX file
        project = import_xlsx_file(file_path)
        if project:
            # Replace current project
            self.project.name = project.name
            project.renumber_task_ids()
            logger.info("Imported %d task(s) from %s", len(project.tasks), file_path)
            self.project.tasks = project.tasks
            self.project.start_date = project.start_date
            self.project.end_date = project.end_date

            # Clear undo/redo history when importing
            if self.undo_redo_manager:
                self.undo_redo_manager.clear()
                self.update_undo_redo_buttons()

            if self.on_project_changed:
                self.on_project_changed()

            messagebox.showinfo("Success", f"Imported {len(project.tasks)} tasks from XLSX file")
        else:
            messagebox.showerror(
                "Error",
                "Failed to import XLSX file.\n\n"
                "Check that openpyxl is installed and that the sheet has a "
                "header row naming a task column plus a start date or duration."
            )

    def export_mermaid(self):
        """Export the current project to a Mermaid (.mmd) file."""
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".mmd",
            filetypes=[("Mermaid Files", "*.mmd"), ("All Files", "*.*")],
            title="Export Mermaid File"
        )
        
        if not file_path:
            return
        
        # Export project to Mermaid
        if export_project_to_mermaid(self.project, file_path):
            messagebox.showinfo("Success", "Project exported to Mermaid successfully!")
        else:
            messagebox.showerror("Error", "Failed to export project to Mermaid")
    
    def export_svg(self):
        """Export the Gantt chart to a scalable SVG file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG Files", "*.svg"), ("All Files", "*.*")],
            title="Export Gantt Chart to SVG"
        )

        if not file_path:
            return

        from gantt_app.utils.image_export import export_gantt_to_svg

        logger.info("Exporting the Gantt chart to SVG: %s", file_path)
        settings = self.gantt_chart._figure_settings() if self.gantt_chart else None
        if export_gantt_to_svg(self.project, file_path, settings=settings):
            messagebox.showinfo("Success", "Gantt chart exported to SVG successfully!")
        else:
            messagebox.showerror(
                "Error",
                "Failed to export the Gantt chart to SVG.\n\n"
                "See the Log window for details."
            )

    def export_png(self):
        """Export the Gantt chart to a PNG file."""
        if self.gantt_chart is None:
            messagebox.showerror("Error", "Gantt chart not available for export")
            return
        
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Files", "*.png"), ("All Files", "*.*")],
            title="Export Gantt Chart to PNG"
        )
        
        if not file_path:
            return
        
        logger.info("Exporting the Gantt chart to PNG: %s", file_path)
        if self.gantt_chart.export_to_png(file_path):
            messagebox.showinfo("Success", "Gantt chart exported to PNG successfully!")
        else:
            self._report_static_export_failure("PNG")
    
    def export_pdf(self):
        """Export the Gantt chart to a PDF file."""
        if self.gantt_chart is None:
            messagebox.showerror("Error", "Gantt chart not available for export")
            return
        
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
            title="Export Gantt Chart to PDF"
        )
        
        if not file_path:
            return
        
        logger.info("Exporting the Gantt chart to PDF: %s", file_path)
        if self.gantt_chart.export_to_pdf(file_path):
            messagebox.showinfo("Success", "Gantt chart exported to PDF successfully!")
        else:
            self._report_static_export_failure("PDF")

    def _report_static_export_failure(self, image_format: str):
        """
        Explain why a PNG or PDF export did not produce a file.

        DEVELOPMENT NOTES:
        ------------------
        This used to import NO_BROWSER_MESSAGE, a constant describing how to
        install a browser for Kaleido. Kaleido went away when exports moved to
        Pillow and the constant went with it, so this function - the one that
        runs when an export fails - raised ImportError and replaced the error
        dialog with a crash.

        Rendering is now Pillow only, so the sole way it can be unavailable is
        Pillow itself missing, which cannot happen in a packaged build.
        """
        from gantt_app.utils.image_export import static_export_available

        if not static_export_available():
            logger.warning("%s export unavailable: Pillow is missing",
                           image_format)
            messagebox.showwarning(
                f"{image_format} Export Unavailable",
                "Image export needs the Pillow library, which is not "
                "available.\n\nExport the chart as HTML instead."
            )
            return

        messagebox.showerror(
            "Error",
            f"Failed to export the Gantt chart to {image_format}.\n\n"
            "See the Log window for details."
        )

    def export_html(self):
        """Export the Gantt chart to a standalone interactive HTML file."""
        if self.gantt_chart is None:
            messagebox.showerror("Error", "Gantt chart not available for export")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")],
            title="Export Gantt Chart to HTML"
        )

        if not file_path:
            return

        from gantt_app.utils.image_export import export_gantt_to_html

        logger.info("Exporting the Gantt chart to HTML: %s", file_path)
        if export_gantt_to_html(self.project, file_path,
                                settings=self.gantt_chart._figure_settings()):
            messagebox.showinfo(
                "Success",
                "Gantt chart exported to HTML.\n\n"
                "The file is self-contained and stays interactive offline."
            )
        else:
            messagebox.showerror(
                "Error",
                "Failed to export the Gantt chart to HTML.\n\n"
                "See the Log window for details."
            )
    
    def export_xlsx(self):
        """Export the project to an Excel XLSX file."""
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            title="Export Project to XLSX"
        )
        
        if not file_path:
            return
        
        # Export project to XLSX
        if export_project_to_xlsx(self.project, file_path):
            messagebox.showinfo("Success", "Project exported to XLSX successfully!")
        else:
            messagebox.showerror(
                "Error",
                "Failed to export project to XLSX.\n\n"
                "Check that openpyxl is installed."
            )
    
    def set_gantt_chart(self, gantt_chart):
        """Set the Gantt chart reference for export functionality."""
        self.gantt_chart = gantt_chart
    
    def set_undo_redo_manager(self, manager: UndoRedoManager):
        """Set the undo/redo manager."""
        self.undo_redo_manager = manager
        self.update_undo_redo_buttons()
    
    def update_undo_redo_buttons(self):
        """Update the state of undo and redo buttons."""
        if self.undo_redo_manager:
            # Update button states if they exist (they may be in dropdown menus now)
            if hasattr(self, 'undo_btn') and self.undo_btn:
                self.undo_btn.configure(state=tk.NORMAL if self.undo_redo_manager.can_undo() else tk.DISABLED)
            if hasattr(self, 'redo_btn') and self.redo_btn:
                self.redo_btn.configure(state=tk.NORMAL if self.undo_redo_manager.can_redo() else tk.DISABLED)
    
    def undo(self):
        """Undo the last action."""
        if self.undo_redo_manager and self.undo_redo_manager.can_undo():
            if self.undo_redo_manager.undo():
                logger.info("Undo")
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
    
    def redo(self):
        """Redo the last undone action."""
        if self.undo_redo_manager and self.undo_redo_manager.can_redo():
            if self.undo_redo_manager.redo():
                logger.info("Redo")
                self.update_undo_redo_buttons()
                if self.on_project_changed:
                    self.on_project_changed()
    
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        current_theme = ctk.get_appearance_mode()
        new_theme = "dark" if current_theme == "light" else "light"
        ctk.set_appearance_mode(new_theme)
        logger.info("Switched appearance to %s mode", new_theme)
    
    def open_gantt_chart_settings(self):
        """Open the Gantt chart settings dialog."""
        if self.gantt_chart:
            from gantt_app.views.ganttsettingsw import GanttChartSettingsDialog
            
            try:
                dialog = GanttChartSettingsDialog(
                    self.master, 
                    self.gantt_chart,
                    on_settings_changed=self._on_gantt_settings_changed
                )
                dialog.wait_window()
            except Exception as e:
                logger.exception("Could not open Gantt chart settings")
                messagebox.showerror(
                    "Settings Error",
                    f"Could not open Gantt chart settings:\n{e}"
                )
        else:
            messagebox.showerror(
                "Error",
                "Gantt chart is not available. Cannot open settings."
            )
    
    def _on_gantt_settings_changed(self, settings: Dict):
        """Handle Gantt chart settings changes."""
        logger.debug("Gantt chart settings changed: %s", settings)
        # The chart will be redrawn automatically by the settings dialog
    
    def set_project(self, project: Project):
        """Set a new project for the toolbar."""
        self.project = project
        
    def copy_tasks(self):
        """Copy selected tasks to clipboard."""
        if self.clipboard_manager and hasattr(self.task_list, 'get_selected_task_ids'):
            selected_ids = self.task_list.get_selected_task_ids()
            if selected_ids:
                self.clipboard_manager.copy(selected_ids)
                logger.info("Copied %d tasks to clipboard", len(selected_ids))
        
    def cut_tasks(self):
        """Cut selected tasks to clipboard."""
        if self.clipboard_manager and hasattr(self.task_list, 'get_selected_task_ids'):
            selected_ids = self.task_list.get_selected_task_ids()
            if selected_ids:
                self.clipboard_manager.cut(selected_ids)
                logger.info("Cut %d tasks to clipboard", len(selected_ids))
        
    def paste_tasks(self):
        """Paste tasks from clipboard."""
        if self.clipboard_manager and self.clipboard_manager.can_paste():
            # Get the target container - for now, paste to root (None)
            target_container_id = None
            if hasattr(self.task_list, 'get_selected_task_ids'):
                selected_ids = self.task_list.get_selected_task_ids()
                if selected_ids:
                    # Paste as child of selected task if one is selected
                    target_container_id = selected_ids[0]
            
            self.clipboard_manager.paste(target_container_id)
            logger.info("Pasted tasks from clipboard")
            
            if self.on_project_changed:
                self.on_project_changed()
        
    def set_task_list(self, task_list):
        """Set the task list reference for copy/paste operations."""
        self.task_list = task_list
        if hasattr(self, 'icon_toolbar'):
            self.icon_toolbar.set_task_list(task_list)


class IconToolbar(ctk.CTkFrame):
    """
    Graphical toolbar with icon buttons for the Gantt application.
    
    This toolbar displays icons for common actions and replaces the text-based menu bar
    with a more visual interface similar to standard toolbar designs.
    
    Icons are generated SVG icons that are open source and unique.
    """
    
    #: Icon size in pixels
    ICON_SIZE = 20
    BUTTON_SIZE = 32
    
    # Icon size in pixels
    # Note: We use emoji icons as a cross-platform fallback
    # The SVG paths are available in gantt_app.resources.icons for future use
    
    def __init__(self, master, project: Project,
                 on_project_changed: Callable[[], None] = None,
                 undo_redo_manager: UndoRedoManager = None,
                 clipboard_manager=None,
                 **kwargs):
        super().__init__(master, height=40, fg_color=WIN_MENU_BG, **kwargs)
        
        self.master = master
        self.project = project
        self.on_project_changed = on_project_changed
        self.undo_redo_manager = undo_redo_manager
        self.clipboard_manager = clipboard_manager
        self.task_list = None
        
        # Store button references for state management
        self.icon_buttons = {}
        
        # Import icons from resources
        from gantt_app.resources.icons import (
            ALWAYS_ACTIVE, ACTIVE_WHEN_PROJECT_OPEN, ICON_EMOJIS
        )
        self.ALWAYS_ACTIVE = ALWAYS_ACTIVE
        self.ACTIVE_WHEN_PROJECT_OPEN = ACTIVE_WHEN_PROJECT_OPEN
        self.ICON_EMOJIS = ICON_EMOJIS
        
        # Create UI
        self._create_ui()
        
        # Update button states
        self._update_button_states()
    
    def _create_ui(self):
        """Create the icon toolbar user interface."""
        # Icon button order based on screenshot: 
        # folder, floppy, clock, person, X, i, scissors, copy, paste, undo, redo
        # Modified per user request:
        # folder (open), floppy (save), edit (replaces i), 
        # task (replaces clock), milestone (replaces person), 
        # delete (X), cut (scissors), copy, paste, undo, redo
        
        icon_order = [
            ('open', 'Open Project', 'load_project'),
            ('new_project', 'New Project', 'new_project'),
            ('save', 'Save Project', 'save_project'),
            ('edit', 'Edit', 'edit_project_info'),
            ('task', 'Create Task', 'add_task'),
            ('subtask', 'Create Subtask', 'add_subtask'),
            ('milestone', 'Create Milestone', 'add_milestone'),
            ('cut', 'Cut', 'cut_tasks'),
            ('copy', 'Copy', 'copy_tasks'),
            ('paste', 'Paste', 'paste_tasks'),
            ('delete', 'Delete', 'delete_selected'),
            ('undo', 'Undo', 'undo'),
            ('redo', 'Redo', 'redo'),
        ]

        # Named, and looked up when the button is pressed.
        #
        # Handed self.add_task here instead, each button kept the bound
        # method it was built with, and Toolbar._connect_icon_toolbar - which
        # puts the real handlers in place afterwards - changed nothing the
        # buttons could see. Every icon ran this class's own stub: pressing
        # Create Task added a task called "New Task" with no dialog and no
        # undo behind it, and Open and Save opened their own file choosers
        # rather than the application's.
        for icon_name, tooltip, method in icon_order:
            self._create_icon_button(
                icon_name, tooltip,
                lambda name=method: getattr(self, name)(),
            )
    
    def _create_icon_button(self, icon_name: str, tooltip: str, command: Callable):
        """
        Create a single icon button.
        
        PARAMETERS:
        -----------
        icon_name : str
            Name of the icon
        tooltip : str
            Tooltip text for the button
        command : Callable
            Function to call when button is clicked
        """
        # Create frame for the button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="left", padx=1, pady=2)
        
        # Get emoji icon
        icon_char = self.ICON_EMOJIS.get(icon_name, '?')
        
        # Create button with emoji icon
        # Use a larger font for better visibility
        try:
            # Try using the system emoji font
            font = ("Segoe UI Emoji", 16)
        except:
            font = ("Arial", 16)
        
        btn = ctk.CTkButton(
            btn_frame,
            text=icon_char,
            width=self.BUTTON_SIZE,
            height=self.BUTTON_SIZE,
            fg_color="transparent",
            hover_color=WIN_MENU_HOVER,
            corner_radius=4,
            command=command,
            font=font
        )
        
        btn.pack(side="left", padx=2, pady=2)
        btn.tooltip = tooltip  # Store tooltip for future use
        
        # Store button reference
        self.icon_buttons[icon_name] = btn
    
    def _update_button_states(self):
        """
        Update the enabled/disabled state of all icon buttons.
        
        Buttons are active when there's an open or new project plan,
        except the Open button which is always active.
        """
        has_project = self.project is not None
        
        for icon_name, btn in self.icon_buttons.items():
            if icon_name in self.ALWAYS_ACTIVE:
                # Always active
                btn.configure(state="normal")
            elif icon_name in self.ACTIVE_WHEN_PROJECT_OPEN:
                # Active only when project is open
                btn.configure(state="normal" if has_project else "disabled")
            else:
                # Default: active when project is open
                btn.configure(state="normal" if has_project else "disabled")
    
    def set_task_list(self, task_list):
        """Set the task list reference for copy/paste operations."""
        self.task_list = task_list
        self._update_button_states()
    
    # Methods for button actions
    def new_project(self):
        """Create a new project."""
        if hasattr(self, '_new_project_impl'):
            self._new_project_impl()
        else:
            # Default implementation
            self.project = Project(name="New Project")
            if self.on_project_changed:
                self.on_project_changed()
            self._update_button_states()
    
    def load_project(self):
        """Load a project from file."""
        if hasattr(self, '_load_project_impl'):
            self._load_project_impl()
        else:
            file_path = filedialog.askopenfilename(
                filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
                title="Open Project"
            )
            if file_path:
                try:
                    self.project = load_project(file_path)
                    if self.on_project_changed:
                        self.on_project_changed()
                    self._update_button_states()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load project: {e}")
    
    def save_project(self):
        """Save the current project."""
        if hasattr(self, '_save_project_impl'):
            self._save_project_impl()
        else:
            if self.project:
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
                    title="Save Project"
                )
                if file_path:
                    try:
                        save_project(self.project, file_path)
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to save project: {e}")
    
    def edit_project_info(self):
        """Edit project information."""
        if hasattr(self, '_edit_project_info_impl'):
            self._edit_project_info_impl()
        else:
            # Default implementation
            if self.project:
                new_name = simpledialog.askstring("Edit Project", "Project Name:", 
                                                   initialvalue=self.project.name)
                if new_name:
                    self.project.name = new_name
                    if self.on_project_changed:
                        self.on_project_changed()
    
    def add_task(self):
        """Add a new task."""
        if hasattr(self, '_add_task_impl'):
            self._add_task_impl()
        else:
            if self.project:
                from gantt_app.models import Task
                task = Task.create_task(name="New Task")
                self.project.add_task(task)
                if self.on_project_changed:
                    self.on_project_changed()
    
    def add_subtask(self):
        """Add a new subtask."""
        if hasattr(self, '_add_subtask_impl'):
            self._add_subtask_impl()
        else:
            self.add_task()  # Default: same as task for now
    
    def add_milestone(self):
        """Add a new milestone."""
        if hasattr(self, '_add_milestone_impl'):
            self._add_milestone_impl()
        else:
            if self.project:
                from gantt_app.models import Task
                task = Task.create_milestone(name="New Milestone")
                self.project.add_task(task)
                if self.on_project_changed:
                    self.on_project_changed()
    
    def cut_tasks(self):
        """Cut selected tasks to clipboard."""
        if self.clipboard_manager and hasattr(self.task_list, 'get_selected_task_ids'):
            selected_ids = self.task_list.get_selected_task_ids()
            if selected_ids:
                self.clipboard_manager.cut(selected_ids)
                self._update_button_states()
    
    def copy_tasks(self):
        """Copy selected tasks to clipboard."""
        if self.clipboard_manager and hasattr(self.task_list, 'get_selected_task_ids'):
            selected_ids = self.task_list.get_selected_task_ids()
            if selected_ids:
                self.clipboard_manager.copy(selected_ids)
                self._update_button_states()
    
    def paste_tasks(self):
        """Paste tasks from clipboard."""
        if self.clipboard_manager and self.clipboard_manager.can_paste():
            target_container_id = None
            if hasattr(self.task_list, 'get_selected_task_ids'):
                selected_ids = self.task_list.get_selected_task_ids()
                if selected_ids:
                    target_container_id = selected_ids[0]
            
            self.clipboard_manager.paste(target_container_id)
            if self.on_project_changed:
                self.on_project_changed()
            self._update_button_states()
    
    def delete_selected(self):
        """Delete selected tasks."""
        if hasattr(self.task_list, 'get_selected_task_ids'):
            selected_ids = self.task_list.get_selected_task_ids()
            if selected_ids and self.project:
                if messagebox.askyesno("Delete", f"Delete {len(selected_ids)} selected task(s)?"):
                    for task_id in selected_ids:
                        self.project.remove_task(task_id)
                    if self.on_project_changed:
                        self.on_project_changed()
    
    def undo(self):
        """Undo the last action."""
        if self.undo_redo_manager:
            self.undo_redo_manager.undo()
            if self.on_project_changed:
                self.on_project_changed()
    
    def redo(self):
        """Redo the last undone action."""
        if self.undo_redo_manager:
            self.undo_redo_manager.redo()
            if self.on_project_changed:
                self.on_project_changed()

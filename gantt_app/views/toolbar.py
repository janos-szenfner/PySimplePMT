"""
Toolbar for the Gantt Project Management Tool.

Contains action buttons for managing the project.
"""

import tkinter as tk
from datetime import datetime
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
from gantt_app.utils.mpp_importer import (
    BINARY_MPP_MESSAGE, import_mpp_file, is_binary_mpp,
)
from gantt_app.utils.mermaid_importer import import_mermaid_file
from gantt_app.utils.xlsx_importer import import_xlsx_file
from gantt_app.utils.mermaid_exporter import export_project_to_mermaid
from gantt_app.utils.xlsx_exporter import export_project_to_xlsx
from gantt_app.utils.gan_exporter import export_project_to_gan
from gantt_app.utils.msproject_exporter import export_project_to_msproject
from gantt_app.utils.undoredo import UndoRedoManager
from gantt_app.views.modal import grab_when_visible
from gantt_app.views.tooltip import attach as attach_tooltip
from gantt_app import theme
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

# The menu bar and its dropdowns. Every one is a (light, dark) pair from
# gantt_app.theme: written as single colours the whole bar stayed light on a
# dark desktop, which is why the window used to be half one thing and half
# the other.
WIN_MENU_BG = theme.MENU_BG
WIN_MENU_HOVER = theme.MENU_HOVER
WIN_MENU_TEXT = theme.MENU_TEXT
WIN_DROPDOWN_BG = theme.DROPDOWN_BG
SEPARATOR_COLOR = theme.ICON_SEPARATOR

#: What a menu entry looks like under the pointer: the application's own
#: blue, which is what every other selected thing here uses. The grey it
#: used to take barely showed which row was about to be chosen.
MENU_HIGHLIGHT = ACCENT
MENU_HIGHLIGHT_TEXT = ACCENT_TEXT


def highlight_on_hover(button, resting_text_color=WIN_MENU_TEXT):
    """
    Make a menu entry light up in blue while the pointer is over it.

    PARAMETERS:
    -----------
    button : ctk.CTkButton
        The entry.
    resting_text_color : str
        What its text goes back to when the pointer leaves.

    DEVELOPMENT NOTES:
    ------------------
    Both colours are set together, in one configure, rather than leaving the
    background to CustomTkinter's own hover and only changing the text.

    Its hover paints the button's inner parts straight onto the canvas, and
    any configure() afterwards redraws the button - which, on a button whose
    fg_color is transparent, paints those same parts back to the background
    colour. Setting only the text therefore rubbed out the very highlight it
    was meant to sit on, and the entry under the pointer turned white on
    white: the row the user was pointing at was the one they could not read.

    hover_color is set to the same blue so that CustomTkinter's own hover,
    which fires first, agrees with what is painted a moment later.
    """
    resting_fg = button.cget("fg_color")

    def enter(_event=None):
        """Light the entry up, background and text in one go."""
        button.configure(fg_color=MENU_HIGHLIGHT,
                         text_color=MENU_HIGHLIGHT_TEXT)

    def leave(_event=None):
        """Put both back."""
        button.configure(fg_color=resting_fg,
                         text_color=resting_text_color)

    button.configure(hover_color=MENU_HIGHLIGHT)
    button.bind("<Enter>", enter, add="+")
    button.bind("<Leave>", leave, add="+")

    # Kept on the button so the effect can be driven without a pointer:
    # a window that is never shown receives no crossing events, so a test
    # cannot hover one.
    button.highlight_enter = enter
    button.highlight_leave = leave


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
        #: The submenu this menu has open, if any, and the row that asked
        #: for it - so asking twice for the same row leaves it alone.
        #: See _handle_submenu.
        self._submenu = None
        self._submenu_row = None
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
            separator = ctk.CTkFrame(row, height=1, fg_color=theme.SEPARATOR, corner_radius=0)
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
            highlight_on_hover(btn)
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
            highlight_on_hover(btn)
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
            highlight_on_hover(btn)
            btn.pack(side="left", fill="x", expand=True)
            
            arrow = ctk.CTkLabel(row, text=">", text_color=theme.SEPARATOR, width=20)
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
        """
        Open a submenu beside the row that asks for it.

        DEVELOPMENT NOTES:
        ------------------
        Where it goes is worked out before anything is torn down. This began
        by calling _close_all_menus, which destroys this menu, and then
        asked the destroyed menu where it was: every press of Create, Import
        or Export raised "bad window path name" and no submenu ever opened.

        Only the submenu already showing is closed. Destroying this menu
        would take the row that was just clicked with it, and the submenu
        being opened is this menu's child.

        Asking twice for the same row does nothing the second time. Both
        hovering a row and clicking it come through here, so a click on a
        row the pointer had already opened used to tear the submenu down and
        build it again - and with the pointer then over neither window, and
        a focus event arriving between the two, what the user saw was a
        click that did nothing. The submenu a row opened stays open until
        another row asks for one.
        """
        if not submenu_items:
            return

        if self._submenu_row is row and self._submenu is not None:
            try:
                if self._submenu.winfo_exists():
                    return
            except tk.TclError:
                pass

        x = self.winfo_rootx() + self.winfo_width() - 4
        y = row.winfo_rooty()

        self._close_submenu()

        self._in_submenu = True
        self._submenu = CTkDropdownMenu(self, items=submenu_items)
        self._submenu_row = row
        self._submenu.geometry(f"+{x}+{y}")
        self._submenu.focus_set()
        self._in_submenu = False

    def _close_submenu(self):
        """Close the submenu this menu has open, if any."""
        submenu = getattr(self, '_submenu', None)
        self._submenu = None
        self._submenu_row = None
        if submenu is None:
            return
        try:
            submenu.destroy()
        except tk.TclError:
            pass

    def _on_submenu_hover(self, submenu_items: List[Dict], row, button):
        """Handle hover to open submenu after a short delay."""
        if not submenu_items:
            return
            
        self._handle_submenu(None, submenu_items, row)

    def _on_focus_out(self):
        """
        Close the menu when the focus leaves it - unless a submenu has it.

        DEVELOPMENT NOTES:
        ------------------
        Whether a submenu is open is asked of the submenu, not of a flag set
        while one is being built. _in_submenu was set True around the two
        lines that make one and cleared immediately afterwards, but the
        focus-out it was guarding against arrives from the event queue after
        those lines have run - so the flag was always False again by the
        time it was read.

        This menu then closed itself the instant its submenu took focus,
        and the submenu went with it, being its child. Opening File or
        Actions looked as though it did nothing at all.
        """
        submenu = getattr(self, '_submenu', None)
        if submenu is not None:
            try:
                if submenu.winfo_exists():
                    return
            except tk.TclError:
                pass
        if self._in_submenu:
            return
        self._close_all_menus()

    def _close_all_menus(self):
        """Close this menu and any submenu under it."""
        self._close_submenu()
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
            highlight_on_hover(btn)
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
        """
        Close the menu when the click lands outside it.

        DEVELOPMENT NOTES:
        ------------------
        Whether the click was inside is answered from the widget's place in
        the tree. This asked winfo_containing, which takes a point on the
        screen and answers which widget is under it - it was handed a window
        id as its only argument, so every click anywhere in the application
        while a menu was open raised TypeError, and the menu did not close.

        A widget's path names its ancestors, so a click inside the dropdown
        or on the button that opened it has that widget's path as a prefix.
        """
        if not self.active_dropdown or not self.active_dropdown.winfo_exists():
            return

        widget = getattr(event, 'widget', None)
        if widget is None or widget is self:
            return

        inside = [self.active_dropdown, *getattr(self, 'menu_buttons', [])]
        if any(self._is_within(widget, part) for part in inside):
            return

        self._close_all_dropdowns()

    @staticmethod
    def _is_within(widget, container) -> bool:
        """Whether a widget is the given one, or sits inside it."""
        try:
            return str(widget) == str(container) or \
                str(widget).startswith(f"{container}.")
        except tk.TclError:
            return False

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
                 clipboard_manager=None,
                 theme_controller=None):
        super().__init__(master)
        
        self.master = master
        self.project = project
        self.on_project_changed = on_project_changed
        self.gantt_chart = gantt_chart
        self.undo_redo_manager = undo_redo_manager
        self.clipboard_manager = clipboard_manager
        #: Who decides light or dark; see gantt_app.theme. Set before the
        #: menus are built, because the View menu is ticked from it. A
        #: toolbar built without one - which the tests do - simply has no
        #: theme entries that do anything.
        self.theme_controller = (
            theme_controller
            or theme.ThemeController(apply=lambda _a: None, persist=False))

        # Set by set_task_list once the list exists, which is after this
        # runs. Left unset, every action that asks what is selected -
        # Copy, Cut, Paste, Delete - raised AttributeError instead of
        # finding nothing selected.
        self.task_list = None

        #: Where the plan was last saved or loaded from, so Save can write
        #: back to it rather than asking every time - which is what it used
        #: to do, making it a second Save As with a different name on it.
        #: None until a file has been chosen; see save_project.
        self.current_file_path = None

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
        # Two rows, one above the other.
        #
        # They used to be packed side by side down one row, each asking to
        # expand, so the menus took half the width and the icons were
        # squeezed into what was left - a strip of empty space with the
        # buttons crushed at one end of it.
        #
        # They are different things and read as different things: the menu
        # bar names everything the application can do, the way a menu bar on
        # any desktop does, and the action bar under it carries the handful
        # of actions worth reaching for without opening a menu.
        menu_config = self._convert_to_new_menu_format()

        self.menu_row = ctk.CTkFrame(self, fg_color=WIN_MENU_BG,
                                     corner_radius=0)
        self.menu_row.pack(side=tk.TOP, fill=tk.X)

        self.menu_bar = CustomMenuBar(self.menu_row, menu_config=menu_config)
        self.menu_bar.pack(side=tk.LEFT)

        # The Log button sits at the end of the menu row, away from the
        # actions, being a thing to look at rather than a thing to do
        self._create_theme_log_buttons()

        self.icon_toolbar = IconToolbar(
            self, self.project,
            on_project_changed=self.on_project_changed,
            undo_redo_manager=self.undo_redo_manager,
            clipboard_manager=self.clipboard_manager,
            theme_controller=self.theme_controller,
        )
        self.icon_toolbar.pack(side=tk.TOP, fill=tk.X)

        self._connect_icon_toolbar()
    
    #: Icon actions whose handler is not a method of this class by that name.
    ICON_HANDLER_OVERRIDES = {
        'delete_selected': '_delete_selected_tasks',
    }

    def _connect_icon_toolbar(self):
        """
        Give every icon in the row the handler it names.

        DEVELOPMENT NOTES:
        ------------------
        Driven from IconToolbar.ICON_ACTIONS rather than from a list written
        out here. The two were maintained by hand and drifted the first time
        an icon was added: the critical path icon was in the row, drawn and
        enabled, and nothing was connected behind it - so pressing it logged
        a line and did nothing while the same action worked from the menu.

        An action with no method to connect is reported rather than passed
        over, since that is exactly the failure this replaced.
        """
        if not hasattr(self, 'icon_toolbar'):
            return

        missing = []
        for _icon, _tooltip, action in self.icon_toolbar.ICON_ACTIONS:
            if not action:
                continue                    # a divider
            name = self.ICON_HANDLER_OVERRIDES.get(action, action)
            handler = getattr(self, name, None)
            if not callable(handler):
                missing.append(action)
                continue
            setattr(self.icon_toolbar, action, handler)

        if missing:
            logger.error("Icon actions with no handler on the toolbar: %s",
                         ', '.join(missing))

        # The formatting bar and the progress group are not in ICON_ACTIONS
        # - they are groups of controls rather than one icon each - so their
        # handlers are connected here
        self.icon_toolbar.apply_task_style = self.apply_task_style
        self.icon_toolbar.set_task_progress = self.set_task_progress
        self.icon_toolbar.mark_on_track = self.mark_on_track
    
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
                    {"text": "Save Project As...", "command": self.save_project_as},
                ],
            },
            {
                'text': 'File',
                'items': [
                    {"text": "Import", "submenu": [
                        {"text": "MS Project...", "command": self.import_mpp},
                        {"text": "GAN...", "command": self.import_gan},
                        {"text": "Mermaid...", "command": self.import_mermaid},
                        {"text": "XLSX...", "command": self.import_xlsx},
                    ]},
                    {"text": "Export", "submenu": [
                        {"text": "GAN...", "command": self.export_gan},
                        {"text": "MS Project...", "command": self.export_msproject},
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
                    {"text": "Calendar Settings...", "command": self.edit_holidays},
                    {"text": "Critical Path...", "command": self.show_critical_path},
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
                    {"text": "System UI mode", "submenu": [
                        {"text": "Sync with system",
                         "command": self.use_system_theme},
                        {"text": "Always Day (light)",
                         "command": self.use_light_theme},
                        {"text": "Always Night (dark)",
                         "command": self.use_dark_theme},
                    ]},
                    {"text": "Settings...", "command": self.open_gantt_chart_settings},
                    {"text": "Help", "command": self.show_help},
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
        """Create the log button, at the far end of the menu row."""
        theme_frame = ctk.CTkFrame(self.menu_row, fg_color='transparent')
        theme_frame.pack(side=tk.RIGHT, padx=5)

        # Log viewer
        self.log_button = ctk.CTkButton(
            theme_frame, text="Log",
            command=self.show_log, width=70,
            fg_color=LOG_ACCENT,
            hover_color=LOG_ACCENT_HOVER,
            text_color="white"
        )
        self.log_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.log_button.tooltip_widget = attach_tooltip(
            self.log_button, "Log - what the application has been doing")

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
    
    def edit_holidays(self):
        """
        Choose which days the plan works: the countries, and dates by hand.

        DEVELOPMENT NOTES:
        ------------------
        The dialog hands back country codes and date rulings and nothing else;
        what either means is the calendar's - see gantt_app.workdaycalendar.
        Setting them on the project's calendar is enough to change every date
        in the plan, because every date in the plan is worked out through it.

        Applied through Project.set_working_week, set_holiday_countries and
        set_date_overrides rather than by writing to the calendar directly, so
        every task keeps the work it holds and its finish moves instead - see
        those methods. The chart is redrawn afterwards through
        on_project_changed, once, however many of the three actually changed.
        """
        from gantt_app.views.holidaydialog import choose_holidays

        #: Whether any tab moved the plan, so the chart is redrawn once
        #: rather than three times - the callbacks fire back to back on the
        #: same Apply, and the dialog calls `applied` after the last of them.
        changed = []

        def apply_working_week(week):
            """Change which weekdays are worked at all."""
            if week == self.project.calendar.non_working_days:
                return

            if self.project.set_working_week(week):
                logger.info("Project %r now works a %d-day week",
                            self.project.name, 7 - len(week))
                changed.append(True)

        def apply(codes):
            """Observe the chosen countries, and settle the plan on them."""
            if set(codes) == self.project.calendar.countries:
                return

            self.project.set_holiday_countries(codes)
            logger.info("Project %r now observes holidays for %s",
                        self.project.name,
                        ', '.join(sorted(codes)) if codes else 'no countries')
            changed.append(True)

        def apply_overrides(overrides):
            """Take the hand-made rulings, and settle the plan on them."""
            if list(overrides) == self.project.calendar.sorted_overrides():
                return

            self.project.set_date_overrides(overrides)
            logger.info("Project %r now carries %d manual date override(s)",
                        self.project.name, len(overrides))
            changed.append(True)

        def apply_calendars(calendars):
            """Take the edited named calendars, and settle the plan on them."""
            if list(calendars) == list(self.project.calendars):
                return

            self.project.set_calendars(calendars)
            logger.info("Project %r now holds %d named calendar(s)",
                        self.project.name, len(calendars))
            changed.append(True)

        def applied():
            """Redraw once, if any of the tabs actually moved the plan."""
            if changed and self.on_project_changed:
                self.on_project_changed()

        choose_holidays(self.master,
                        sorted(self.project.calendar.countries), apply,
                        self.project.calendar.sorted_overrides(),
                        apply_overrides,
                        self.project.calendar.non_working_days,
                        apply_working_week, applied,
                        self.project.calendars, apply_calendars)

    def show_critical_path(self):
        """
        Open the critical path analysis.

        DEVELOPMENT NOTES:
        ------------------
        The plan is settled first. The analysis measures float against the
        dates as scheduled, so reporting on a plan with an unapplied link in
        it would give float that disappears the moment anything else touches
        the project - and the reader would have no way of telling which
        numbers were which.
        """
        from gantt_app.views.criticalpath import show_critical_path

        if self.project.reschedule() and self.on_project_changed:
            self.on_project_changed()

        show_critical_path(self.master, self.project)

    def save_project(self):
        """
        Save the plan back to the file it came from.

        DEVELOPMENT NOTES:
        ------------------
        This used to open a file chooser every time, which made it a second
        Save As under a different name: saving twice meant picking the same
        file twice and confirming the overwrite. It writes back to
        current_file_path now and only asks when there is nowhere to write -
        a plan that has never been saved, which is the one case where the
        question is the right one.
        """
        if not self.current_file_path:
            self.save_project_as()
            return

        self._write_project(self.current_file_path)

    def save_project_as(self):
        """
        Save the plan to a file chosen now, and keep writing there.

        DEVELOPMENT NOTES:
        ------------------
        The chosen path becomes current_file_path, so this is also how a
        plan that has never been saved acquires one - see save_project,
        which hands over to this rather than asking the question twice.
        """
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save Project As",
            initialfile=f"{self.project.name.replace(' ', '_')}.json",
        )

        if not file_path:
            return

        self._write_project(file_path)

    def _write_project(self, file_path: str):
        """Write the plan to one path, and remember it if that worked."""
        logger.info("Saving project %r to %s", self.project.name, file_path)
        if save_project(self.project, file_path):
            self.current_file_path = file_path
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
            # Save writes back here from now on, rather than asking
            self.current_file_path = file_path
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
            # A new plan has never been saved, so Save has to ask where -
            # writing it over whatever file the last plan came from is the
            # one thing it must not do
            self.current_file_path = None
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
    
    def _selected_task_ids(self):
        """
        What is selected in the task list, or an empty list.

        DEVELOPMENT NOTES:
        ------------------
        The list is set after this toolbar is built - see set_task_list - so
        every action asking what is selected has to cope with there being no
        list yet rather than assuming one.
        """
        task_list = getattr(self, 'task_list', None)
        if task_list is None or not hasattr(task_list, 'get_selected_task_ids'):
            return []
        return list(task_list.get_selected_task_ids() or [])

    def edit_selected_task(self):
        """
        Open the editor for the selected row.

        DEVELOPMENT NOTES:
        ------------------
        The pencil used to open the project title box, which is a different
        thing entirely: a plan has one title and a great many tasks, and the
        icon sitting among the actions that work on a row read as the one
        that edits a row. Renaming the plan is on the Actions menu, where
        the other project-wide settings are.

        One row only. The editor edits a single task, and picking the first
        of several silently would edit something the user did not point at.
        """
        selected = self._selected_task_ids()
        if not selected:
            messagebox.showinfo("Edit Task",
                                "Select the task you want to edit first.")
            return
        if len(selected) > 1:
            messagebox.showinfo(
                "Edit Task",
                "Several tasks are selected. Choose the one to edit.")
            return

        self.task_list.edit_task(selected[0])

    def indent_selected(self):
        """Make the selected rows sub-tasks of the row above them."""
        selected = self._selected_task_ids()
        if not selected:
            messagebox.showinfo("Indent",
                                "Select the task or tasks to indent first.")
            return
        self.task_list.indent_task(selected)

    def outdent_selected(self):
        """Move the selected rows out to sit beside their parent."""
        selected = self._selected_task_ids()
        if not selected:
            messagebox.showinfo("Outdent",
                                "Select the task or tasks to outdent first.")
            return
        self.task_list.outdent_task(selected)

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
        """
        Import a Microsoft Project file.

        DEVELOPMENT NOTES:
        ------------------
        Both Microsoft formats are offered, because somebody choosing this
        does not necessarily know which one they have. MSPDI XML is read in
        full; a binary .mpp cannot be read outside Project, so it is
        identified as one and answered with the step that turns it into a
        file this application can read - see mpp_importer.

        That case gets showinfo rather than showerror. Nothing has gone
        wrong: the file is intact, the user did nothing incorrect, and there
        is a short way forward. An error dialog would say the application
        failed at something it never claimed to do.
        """
        file_path = filedialog.askopenfilename(
            filetypes=[("Microsoft Project Files", "*.xml *.mpp"),
                       ("MS Project XML", "*.xml"),
                       ("MS Project Binary", "*.mpp"),
                       ("All Files", "*.*")],
            title="Import MS Project File"
        )

        if not file_path:
            return

        if is_binary_mpp(file_path):
            logger.info("Declined a binary .mpp: %s", file_path)
            messagebox.showinfo("Save it as XML first", BINARY_MPP_MESSAGE)
            return

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
            
            messagebox.showinfo(
                "Success",
                f"Imported {len(project.tasks)} tasks from the MS Project file"
            )
        else:
            messagebox.showerror(
                "Error",
                "Failed to import the MS Project file.\n\n"
                "See the Log window for details."
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

    def export_gan(self):
        """Export the current project to a GanttProject (.gan) file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".gan",
            filetypes=[("GanttProject Files", "*.gan"), ("All Files", "*.*")],
            title="Export Project to GAN"
        )

        if not file_path:
            return

        logger.info("Exporting the project to GAN: %s", file_path)
        if export_project_to_gan(self.project, file_path):
            messagebox.showinfo("Success", "Project exported to GAN successfully!")
        else:
            messagebox.showerror(
                "Error",
                "Failed to export project to GAN.\n\n"
                "See the Log window for details."
            )

    def export_msproject(self):
        """
        Export the current project to a Microsoft Project (MSPDI) file.

        DEVELOPMENT NOTES:
        ------------------
        The extension is .xml rather than .mpp, and the dialog says so: .mpp
        is an undocumented binary format that only Project itself writes, and
        offering it here would produce a file Project refuses to open. MSPDI
        is Microsoft's own published interchange XML and Project opens it
        directly - so the success message names it, rather than leaving
        somebody looking for the .mpp they thought they asked for.
        """
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("MS Project XML Files", "*.xml"), ("All Files", "*.*")],
            title="Export Project to MS Project XML"
        )

        if not file_path:
            return

        logger.info("Exporting the project to MS Project XML: %s", file_path)
        if export_project_to_msproject(self.project, file_path):
            messagebox.showinfo(
                "Success",
                "Project exported to Microsoft Project XML.\n\n"
                "Open it in MS Project with File > Open; the dates are held "
                "by Start No Earlier Than constraints, so nothing moves "
                "unless you move it."
            )
        else:
            messagebox.showerror(
                "Error",
                "Failed to export project to MS Project XML.\n\n"
                "See the Log window for details."
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
    
    def _set_theme_mode(self, mode: str):
        """
        Put the application into one of the three modes.

        The three entries under View > System UI mode are separate named
        methods rather than one parameterised entry, because every menu leaf
        has to name a real method - see test_every_leaf_names_a_real_method,
        which is what stops an entry pointing at a command that was renamed
        out from under it.
        """
        if self.theme_controller is None:
            return
        self.theme_controller.set_mode(mode)

    def use_system_theme(self):
        """View > System UI mode > Sync with system."""
        self._set_theme_mode(theme.MODE_SYSTEM)

    def use_light_theme(self):
        """View > System UI mode > Always Day."""
        self._set_theme_mode(theme.MODE_LIGHT)

    def use_dark_theme(self):
        """View > System UI mode > Always Night."""
        self._set_theme_mode(theme.MODE_DARK)

    def show_help(self):
        """
        Open the user guide, the same window the ? on the icon bar opens.

        One window, kept as one instance, so reaching it from the menu while
        it is already open raises the copy that is there rather than stacking
        a second one - see ReferenceWindow.show.
        """
        from gantt_app.help.userguide import show_user_guide

        show_user_guide(self.winfo_toplevel())

    def toggle_theme(self):
        """
        Flip between day and night, taking manual control.

        Kept as a method because the Log row's theme button and any caller
        that predates the View submenu still reach for it by name.
        """
        if self.theme_controller is None:
            return
        self.theme_controller.toggle()
    
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
        """
        Set the task list reference for copy/paste operations.

        DEVELOPMENT NOTES:
        ------------------
        Also where the formatting bar starts following the selection. The
        binding is added here rather than at construction because the list
        does not exist yet then, and it is added to the tree's own selection
        event with add='+' so the list's existing handlers are untouched.
        """
        self.task_list = task_list
        if hasattr(self, 'icon_toolbar'):
            self.icon_toolbar.set_task_list(task_list)

        tree = getattr(task_list, 'tree', None)
        if tree is not None:
            try:
                tree.bind('<<TreeviewSelect>>',
                          lambda _event: self.refresh_style_bar(), add='+')
            except tk.TclError:
                logger.debug("Could not follow the task list selection")
        self._bind_style_hotkeys()
        self.refresh_style_bar()

    #: The formatting each hotkey toggles.
    STYLE_HOTKEYS = {
        '<Control-b>': 'bold',
        '<Control-B>': 'bold',
        '<Control-i>': 'italic',
        '<Control-I>': 'italic',
        '<Control-u>': 'underline',
        '<Control-U>': 'underline',
    }

    def _bind_style_hotkeys(self):
        """
        Ctrl+B, Ctrl+I and Ctrl+U, on the window rather than on a widget.

        DEVELOPMENT NOTES:
        ------------------
        Bound to the toplevel so they work wherever the focus is in the
        window, which is the point of a hotkey - a reader who has just
        clicked a row should not have to click something else first.

        Both cases of each letter are bound. Tk reports <Control-B> when
        caps lock is on, and a shortcut that stops working with caps lock is
        the kind of fault nobody reports and everybody notices.
        """
        try:
            window = self.winfo_toplevel()
        except tk.TclError:
            return

        for sequence, name in self.STYLE_HOTKEYS.items():
            window.bind(sequence,
                        lambda _event, kind=name: self._hotkey_style(kind),
                        add='+')

    def _hotkey_style(self, kind: str):
        """Toggle one emphasis from the keyboard, if anything is selected."""
        bar = getattr(getattr(self, 'icon_toolbar', None), 'style_bar', None)
        if bar is None or not bar.enabled:
            return 'break'
        self.apply_task_style(kind, not getattr(bar, f"_{kind}_on", False))
        return 'break'

    def _selected_style(self):
        """
        What the selected rows look like now, as one answer.

        RETURNS:
        --------
        Optional[ResolvedStyle]
            None when nothing is selected. Where the selection disagrees,
            the common ground: an emphasis is shown as on only when every
            selected row has it, and a colour only when they all carry the
            same one.

        DEVELOPMENT NOTES:
        ------------------
        Showing the first row's formatting for a mixed selection would be a
        lie about the other rows, and pressing B would then appear to turn
        bold off for rows that never had it. Common ground makes the press
        mean "make them all bold", which is what a reader intends.
        """
        from gantt_app.taskstyle import ResolvedStyle, resolve

        selected = self._selected_task_ids()
        if not selected:
            return None

        resolved = []
        for task_id in selected:
            task = self.project.get_task_by_id(task_id)
            if task is None:
                continue
            summary = (self.task_list.is_summary_row(task)
                       if hasattr(self.task_list, 'is_summary_row') else False)
            resolved.append(resolve(task.style, summary))

        if not resolved:
            return None

        def shared(name):
            """One value where every row agrees, otherwise nothing."""
            values = {getattr(item, name) for item in resolved}
            return values.pop() if len(values) == 1 else None

        return ResolvedStyle(
            text_color=shared('text_color'),
            fill_color=shared('fill_color'),
            bold=all(item.bold for item in resolved),
            italic=all(item.italic for item in resolved),
            underline=all(item.underline for item in resolved),
        )

    def _apply_updates(self, updates: dict, label: str) -> bool:
        """
        Change several tasks as one undoable step, and redraw.

        PARAMETERS:
        -----------
        updates : dict
            The properties to change, by task ID.
        label : str
            What the change is called in the undo history.

        RETURNS:
        --------
        bool
            True when anything changed.

        DEVELOPMENT NOTES:
        ------------------
        The tracker belongs to the task list, which owns the undo history
        for changes to tasks. Without one - a toolbar built on its own, as
        the tests do - the change is still made, just not recorded.
        """
        if not updates:
            return False

        tracker = getattr(self.task_list, 'project_tracker', None)
        if tracker is not None:
            changed = tracker.update_tasks(updates, label)
        else:
            changed = False
            for task_id, changes in updates.items():
                task = self.project.get_task_by_id(task_id)
                if task is None:
                    continue
                for name, value in changes.items():
                    setattr(task, name, value)
                changed = True

        if changed and self.on_project_changed:
            self.on_project_changed()
        self.update_undo_redo_buttons()
        return changed

    def refresh_style_bar(self):
        """Show the selection's formatting on the bar, or grey it out."""
        bar = getattr(getattr(self, 'icon_toolbar', None), 'style_bar', None)
        if bar is not None:
            try:
                resolved = self._selected_style()
                bar.set_state(resolved is not None, resolved)
            except Exception:
                logger.exception("Could not refresh the formatting bar")

        group = getattr(getattr(self, 'icon_toolbar', None),
                        'progress_group', None)
        if group is not None:
            try:
                group.set_state(bool(self._selected_task_ids()))
            except Exception:
                logger.exception("Could not refresh the progress group")

    def _progress_targets(self, task_ids):
        """
        Which tasks a progress change should actually reach.

        PARAMETERS:
        -----------
        task_ids : Sequence[str]
            What is selected.

        RETURNS:
        --------
        List[str]
            The work items among them, with the work under any selected
            summary included.

        DEVELOPMENT NOTES:
        ------------------
        A summary's completion is rolled up from its children and would be
        overwritten by the next reschedule, so writing a percentage onto one
        does nothing that lasts - see Project.roll_up_summaries. Selecting a
        phase and pressing 100% has an obvious meaning, though, so the work
        beneath it is what gets marked instead of the press being ignored.
        """
        targets = []
        seen = set()

        def add(task_id):
            """One task, or everything under it when it is a summary."""
            task = self.project.get_task_by_id(task_id)
            if task is None or task_id in seen:
                return
            seen.add(task_id)

            children = self.project.get_subtasks(task_id)
            if children:
                for child in children:
                    add(child.id)
            elif not task.is_container:
                targets.append(task_id)

        for task_id in task_ids:
            add(task_id)
        return targets

    def set_task_progress(self, percent: int):
        """
        Set the selected tasks to one of the preset thresholds.

        PARAMETERS:
        -----------
        percent : int
            0, 25, 50, 75 or 100.

        DEVELOPMENT NOTES:
        ------------------
        One entry in the undo history however many rows were marked, and
        rows already at that percentage are left out of it so pressing the
        same button twice does not cost a second undo step.
        """
        selected = self._selected_task_ids()
        targets = self._progress_targets(selected)
        if not targets:
            if selected:
                messagebox.showinfo(
                    "Progress",
                    "The selected rows have no work under them to mark.")
            return

        percent = max(0, min(100, int(percent)))
        updates = {task_id: {'progress': percent}
                   for task_id in targets
                   if self.project.get_task_by_id(task_id).progress != percent}

        if not updates:
            return

        self._apply_updates(updates, f"Set {len(updates)} Task(s) to {percent}%")
        logger.info("Set %d task(s) to %d%%", len(updates), percent)
        self.refresh_style_bar()

    def mark_on_track(self, scope: str = 'selected'):
        """
        Set tasks to where today's date says they should have got to.

        PARAMETERS:
        -----------
        scope : str
            'selected' for the selected rows, 'project' for the whole plan.

        DEVELOPMENT NOTES:
        ------------------
        Today is the status date. The specification allows for one named by
        the reader instead, and there is nowhere to name it yet - so this
        says which date it used in the log and in the message, rather than
        leaving somebody to guess what "on track" was measured against.
        """
        from gantt_app.views.progressgroup import SCOPE_PROJECT

        status_date = datetime.now()

        if scope == SCOPE_PROJECT:
            targets = self._progress_targets(
                [task.id for task in self.project.tasks])
        else:
            targets = self._progress_targets(self._selected_task_ids())

        if not targets:
            messagebox.showinfo(
                "Mark on Track",
                "There is no work to mark. Select some tasks, or choose "
                "Entire Project from the arrow beside the button.")
            return

        updates = {}
        for task_id in targets:
            task = self.project.get_task_by_id(task_id)
            expected = self.project.progress_on_track(task, status_date)
            if task.progress != expected:
                updates[task_id] = {'progress': expected}

        if not updates:
            messagebox.showinfo(
                "Mark on Track",
                f"Everything is already where {status_date:%d %b %Y} says "
                f"it should be.")
            return

        self._apply_updates(updates, f"Mark {len(updates)} Task(s) on Track")
        logger.info("Marked %d task(s) on track against %s",
                    len(updates), status_date.date())
        self.refresh_style_bar()

    def apply_task_style(self, kind: str, value):
        """
        Apply one formatting change to every selected row.

        PARAMETERS:
        -----------
        kind : str
            'bold', 'italic', 'underline', 'text_color', 'fill_color',
            'preset' or 'reset'.
        value : object
            What to set it to. A TaskStyle for 'preset', ignored for
            'reset'.

        DEVELOPMENT NOTES:
        ------------------
        Through the tracker's batch update, so the whole change is one entry
        in the undo history: marking forty rows and pressing undo once puts
        all forty back.

        This used to call update_task in a loop, which executes a command
        per call - so it made forty entries and Undo put back one row per
        press, while a comment here said otherwise. See
        ProjectStateTracker.update_tasks.
        """
        from gantt_app.taskstyle import TaskStyle

        selected = self._selected_task_ids()
        if not selected:
            return

        updates = {}
        for task_id in selected:
            task = self.project.get_task_by_id(task_id)
            if task is None:
                continue

            if kind == 'reset':
                style = TaskStyle()
            elif kind == 'preset':
                style = TaskStyle.from_any(value)
            else:
                style = task.style.with_changes(**{kind: value})

            # A row already carrying it adds nothing to undo
            if style != task.style:
                updates[task_id] = {'style': style}

        if not updates:
            return

        self._apply_updates(updates, f"Format {len(updates)} Task(s)")
        logger.info("Applied %s formatting to %d row(s)", kind, len(updates))
        self.refresh_style_bar()


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

    #: The divider between two groups of icons.
    SEPARATOR_HEIGHT = 22
    SEPARATOR_PAD = 6
    
    # Icon size in pixels
    # Note: We use emoji icons as a cross-platform fallback
    # The SVG paths are available in gantt_app.resources.icons for future use
    
    def __init__(self, master, project: Project,
                 on_project_changed: Callable[[], None] = None,
                 undo_redo_manager: UndoRedoManager = None,
                 clipboard_manager=None,
                 theme_controller=None,
                 **kwargs):
        super().__init__(master, height=40, fg_color=WIN_MENU_BG, **kwargs)
        
        self.master = master
        self.project = project
        self.on_project_changed = on_project_changed
        self.undo_redo_manager = undo_redo_manager
        self.clipboard_manager = clipboard_manager
        #: Set before _create_ui runs, which builds the day/night control
        #: from it. A row built without one still draws the control; it just
        #: has nothing behind it - see _theme_controller.
        self.theme_controller = (
            theme_controller
            or theme.ThemeController(apply=lambda _a: None, persist=False))
        self.task_list = None
        
        # Store button references for state management
        self.icon_buttons = {}
        #: One CTkImage per icon name, built once; see _icon_image.
        self._icon_images = {}
        #: The dividers between groups, kept so they can be found again
        self.separators = []
        
        # Which icons are live with no project open, and which need one
        from gantt_app.resources.icons import (
            ALWAYS_ACTIVE, ACTIVE_WHEN_PROJECT_OPEN
        )
        self.ALWAYS_ACTIVE = ALWAYS_ACTIVE
        self.ACTIVE_WHEN_PROJECT_OPEN = ACTIVE_WHEN_PROJECT_OPEN
        
        # Create UI
        self._create_ui()
        
        # Update button states
        self._update_button_states()
    
    #: The icons along the row, in order: the icon's name, its tooltip, and
    #: the action it stands for.
    #:
    #: The action is a name, looked up when the button is pressed. The
    #: handlers themselves belong to Toolbar, which puts them here through
    #: _connect_icon_toolbar once this row is built - so binding a method of
    #: this class to a button would bind the wrong thing, and did.
    #: The name standing in for a divider rather than a button.
    SEPARATOR = 'separator'

    #: What the ? keeps clear of the right edge, so it lands under the Log
    #: button on the row above.
    #:
    #: Where the centre of the Log button sits, measured in from the right
    #: edge of the toolbar: it is 70 wide and keeps 10px clear.
    LOG_CENTRE_FROM_RIGHT = 10 + 70 // 2

    #: What the ? keeps clear of the right edge so its own centre lands on
    #: that same line. Both rows fill the toolbar's width, which is what
    #: makes the two measurements comparable at all.
    HELP_RIGHT_PAD = LOG_CENTRE_FROM_RIGHT - BUTTON_SIZE // 2

    ICON_ACTIONS = (
        ('save', 'Save Project', 'save_project'),
        ('save_as', 'Save Project As...', 'save_project_as'),
        (SEPARATOR, '', ''),
        # Editing the selected row, then moving it between levels. The three
        # act on what is selected in the task list, which is why they sit
        # together and apart from the file actions.
        ('edit', 'Edit Task...', 'edit_selected_task'),
        ('indent', 'Indent Task', 'indent_selected'),
        ('outdent', 'Outdent Task', 'outdent_selected'),
        (SEPARATOR, '', ''),
        # Set apart on both sides: it neither creates anything nor moves
        # anything about, so it belongs to neither group it sits between
        ('critical_path', 'Critical Path Analysis', 'show_critical_path'),
        (SEPARATOR, '', ''),
        ('cut', 'Cut', 'cut_tasks'),
        ('copy', 'Copy', 'copy_tasks'),
        ('paste', 'Paste', 'paste_tasks'),
        ('delete', 'Delete', 'delete_selected'),
        ('undo', 'Undo', 'undo'),
        ('redo', 'Redo', 'redo'),
    )

    #: The icon the formatting group is placed after.
    #:
    #: Held as a name rather than an index so the row can be reordered
    #: without silently putting the group somewhere else.
    STYLE_GROUP_AFTER = 'outdent'

    def _create_ui(self):
        """Build the row of icon buttons, divided into its groups."""
        for icon_name, tooltip, action in self.ICON_ACTIONS:
            if icon_name == self.SEPARATOR:
                self._create_separator()
                continue
            self._create_icon_button(
                icon_name, tooltip,
                lambda name=action: self._perform(name),
            )
            if icon_name == self.STYLE_GROUP_AFTER:
                self._create_style_bar()

        self._create_separator()
        self._create_search_box()
        self._create_separator()
        self._create_theme_control()
        self._create_help_button()

    def _create_style_bar(self):
        """
        The formatting group, held apart from the row on both sides.

        DEVELOPMENT NOTES:
        ------------------
        A divider either side because this is a different kind of control
        from everything around it: the rest of the row does something to the
        plan, and these change how the plan is drawn. Wedged against the
        buttons that indent and outdent, the B would read as another action
        on the task rather than as the start of a group.

        The drawings come from this row's own cache, so the highlighter and
        the tag are painted once per appearance like every other icon rather
        than twice.
        """
        from gantt_app.views.stylebar import StyleBar

        self._create_separator()
        self.style_bar = StyleBar(
            self, on_apply=self._style_applied,
            button_size=self.BUTTON_SIZE, icon_image=self._icon_image)
        self.style_bar.pack(side="left", padx=(1, 1), pady=0)
        self._create_separator()
        self._create_progress_group()

    def _create_progress_group(self):
        """
        The progress controls, held apart from the row on both sides.

        DEVELOPMENT NOTES:
        ------------------
        Beside the formatting group and after it, because the two are what a
        reader does to a row they have already picked out: mark it up, then
        say where it has got to. Both are separated from the actions that
        change the plan's shape.
        """
        from gantt_app.views.progressgroup import ProgressGroup

        self.progress_group = ProgressGroup(
            self, on_preset=self._progress_applied,
            on_mark_on_track=self._mark_on_track_applied,
            button_size=self.BUTTON_SIZE, icon_image=self._icon_image)
        self.progress_group.pack(side="left", padx=(1, 1), pady=0)
        self._create_separator()

    def _progress_applied(self, percent: int):
        """Hand a threshold to whoever knows what is selected."""
        handler = getattr(self, 'set_task_progress', None)
        if not callable(handler):
            logger.warning("The progress group has no handler connected")
            return
        handler(percent)

    def _mark_on_track_applied(self, scope: str):
        """Hand a Mark on Track to whoever knows what is selected."""
        handler = getattr(self, 'mark_on_track', None)
        if not callable(handler):
            logger.warning("The progress group has no handler connected")
            return
        handler(scope)

    def _style_applied(self, kind: str, value):
        """
        Hand a formatting change to whoever knows what is selected.

        DEVELOPMENT NOTES:
        ------------------
        Connected by Toolbar the same way every other action here is, and
        for the same reason - this row has no task list and no undo history
        of its own. A row built without a Toolbar says so rather than
        half-applying anything; see _perform.
        """
        handler = getattr(self, 'apply_task_style', None)
        if not callable(handler):
            logger.warning("The formatting bar has no handler connected")
            return
        handler(kind, value)

    def _create_search_box(self):
        """
        The box that finds a row by anything written on it.

        DEVELOPMENT NOTES:
        ------------------
        Set apart from the action icons by a divider on each side: it neither
        creates anything nor moves anything about, and a text box wedged
        against a row of buttons reads as one of them.

        What it hides is the task list's business - see
        DragDropTaskList.apply_search. This only says what was typed and
        reports back how much of the plan is left, which is the count the
        reader needs to know a short list is a filtered one.
        """
        from gantt_app.views.searchbox import TaskSearchBox

        self.search_box = TaskSearchBox(self, on_search=self._search_tasks)
        self.search_box.pack(side="left", padx=(2, 2), pady=2)

    def _search_tasks(self, needle: str):
        """Hide every row that does not carry the text, and say how many."""
        task_list = getattr(self, 'task_list', None)
        if task_list is None or not hasattr(task_list, 'apply_search'):
            return

        try:
            shown, total = task_list.apply_search(needle)
        except Exception:
            logger.exception("Could not apply the task search")
            return

        self.search_box.report(shown, total)

    def _create_help_button(self):
        """
        The ? that opens the full guide.

        Built here rather than listed in ICON_ACTIONS because it needs no
        project and no handler connected from Toolbar - it opens a window
        that reads nothing. Everything in ICON_ACTIONS is greyed out with no
        plan open, and help that is unavailable until you have a project is
        help withheld from exactly the person who needs it.
        """
        self.help_button = ctk.CTkButton(
            self, text="" , width=self.BUTTON_SIZE, height=self.BUTTON_SIZE,
            fg_color="transparent", hover_color=WIN_MENU_HOVER,
            text_color=WIN_MENU_TEXT, corner_radius=4,
            command=self.show_help,
        )
        image = self._icon_image('help')
        if image is not None:
            self.help_button.configure(image=image)
            self.help_button.icon_image = image
        else:
            self.help_button.configure(text="?")
        self.help_button.tooltip = "Help"
        self.help_button.tooltip_widget = attach_tooltip(
            self.help_button, "Help - open the user guide")
        # Packed to the right rather than after the day/night control, so it
        # sits under the Log button on the menu row above. Both rows fill the
        # toolbar's width, so lining the two up is a matter of matching what
        # each keeps clear of the right edge - see HELP_RIGHT_PAD.
        self.help_button.pack(side="right", padx=(2, self.HELP_RIGHT_PAD),
                              pady=2)

    def show_help(self):
        """Open the user guide, or raise the copy already open."""
        from gantt_app.help.userguide import show_user_guide

        show_user_guide(self.winfo_toplevel())

    # ---- the day / night control ----------------------------------------

    def _create_theme_control(self):
        """
        The sun/moon toggle, and the way back to following the desktop.

        DEVELOPMENT NOTES:
        ------------------
        Two widgets, and the second one is usually not there. The toggle is
        always shown and says which appearance the window is *in* - a sun and
        Day while light, a moon and Night while dark. "Sync with system" is
        packed only while a manual choice is in force, because that is the
        only time it does anything: offered permanently it is a button that
        is a no-op on the default setting, and it is exactly the sort of
        chrome that makes a toolbar unreadable.

        Its presence is also the status indicator. A window following the
        desktop looks like it always did; one that has been overridden grows
        a control saying so, which is a quieter way of saying "manual" than a
        permanent badge nobody reads after the first day.
        """
        self.theme_button = ctk.CTkButton(
            self, text="", width=86, height=self.BUTTON_SIZE,
            fg_color="transparent", hover_color=WIN_MENU_HOVER,
            text_color=WIN_MENU_TEXT, corner_radius=4, anchor="w",
            command=self._toggle_theme,
        )
        self.theme_button.pack(side="left", padx=2, pady=2)

        self.theme_sync_button = ctk.CTkButton(
            self, text="Sync with system", width=124,
            height=self.BUTTON_SIZE, fg_color="transparent",
            hover_color=WIN_MENU_HOVER, text_color=theme.MUTED_TEXT,
            corner_radius=4, command=self._sync_theme,
        )
        # Packed by _refresh_theme_control when a manual choice is in force.
        self.theme_sync_button.tooltip_widget = attach_tooltip(
            self.theme_sync_button,
            "Follow the desktop's own light or dark setting again")

        controller = self._theme_controller()
        if controller is not None:
            # Owned by this row, so the subscription goes when the row
            # does - the controller belongs to the application and outlives
            # any number of toolbars. See ThemeController.subscribe.
            controller.subscribe(
                lambda _mode, _appearance: self._refresh_theme_control(),
                owner=self)
        self._refresh_theme_control()

    def _theme_controller(self):
        """
        The application's theme controller, or None before there is one.

        Looked up rather than held, because this row is built before the
        window has finished assembling itself and a test may build it with no
        application at all.
        """
        return getattr(self, 'theme_controller', None)

    def _toggle_theme(self):
        """Flip between day and night, and take manual control."""
        controller = self._theme_controller()
        if controller is None:
            return
        controller.toggle()

    def _sync_theme(self):
        """Hand the decision back to the desktop."""
        controller = self._theme_controller()
        if controller is None:
            return
        controller.sync_with_system()

    def _refresh_theme_control(self):
        """
        Put the toggle's icon, caption and the sync button in step.

        Guarded, because this is a subscriber: it goes on being called after
        the toolbar it belongs to has been destroyed, and writing to a dead
        widget raises.
        """
        controller = self._theme_controller()
        button = getattr(self, 'theme_button', None)
        if controller is None or button is None:
            return

        try:
            if not button.winfo_exists():
                return
        except tk.TclError:
            return

        image = self._icon_image(controller.icon_name())
        button.configure(text=f" {controller.button_text()}", image=image)
        # Kept from the garbage collector: a collected CTkImage takes the
        # picture off the button with it.
        button.icon_image = image
        button.tooltip = (
            f"{controller.button_text()} mode"
            + ("" if controller.following_system else " (manual)")
        )
        # Rebuilt rather than reworded, because the caption changes every
        # time the mode does and a Tooltip holds the text it was given
        button.tooltip_widget = attach_tooltip(button, button.tooltip)

        sync = getattr(self, 'theme_sync_button', None)
        if sync is None:
            return
        if controller.following_system:
            sync.pack_forget()
        elif not sync.winfo_manager():
            sync.pack(side="left", padx=2, pady=2)

    def _create_separator(self):
        """
        A divider between two groups of icons.

        A hairline rather than a gap: the row runs from making things to
        moving them about, and the two read as one long row of buttons
        without a line to say where one ends.
        """
        divider = ctk.CTkFrame(self, width=1, height=self.SEPARATOR_HEIGHT,
                               fg_color=SEPARATOR_COLOR, corner_radius=0)
        divider.pack(side="left", fill=None, padx=self.SEPARATOR_PAD, pady=6)
        divider.pack_propagate(False)
        self.separators.append(divider)

    def _perform(self, action: str):
        """
        Run the handler Toolbar connected for an icon.

        DEVELOPMENT NOTES:
        ------------------
        This class used to carry a handler of its own for every icon - its
        own file choosers, its own task creation - none of which ever ran.
        Toolbar replaces every one of them in _connect_icon_toolbar, so they
        were a second implementation of the toolbar's actions that no button
        could reach: the copy that skipped the create dialog and the undo
        history sat here unused, and the copy that works sat in Toolbar.

        A row built without a Toolbar to connect it has nothing behind its
        buttons, which is said rather than half-done.
        """
        handler = getattr(self, action, None)
        if not callable(handler):
            logger.warning("The %s icon has no handler connected", action)
            return
        handler()
    
    def _icon_image(self, icon_name: str):
        """
        One icon, drawn once for each appearance.

        RETURNS:
        --------
        Optional[ctk.CTkImage]
            The icon, or None when nothing is defined for the name - the
            caller falls back to a letter.

        DEVELOPMENT NOTES:
        ------------------
        Two drawings, not one. CustomTkinter picks between light_image and
        dark_image by appearance, and this used to hand it the same near-black
        drawing for both - so every icon on the row disappeared into the bar
        the moment the window went dark. Pillow knows nothing about appearance
        modes, so the ink is chosen here and the strokes are drawn twice.

        Drawn rather than set as an emoji in "Segoe UI Emoji": that font ships
        with Windows and with nothing else, so on a stock Linux desktop every
        button on this row came out blank.
        """
        from gantt_app.resources.icons import draw_icon

        cached = self._icon_images.get(icon_name)
        if cached is not None:
            return cached

        light = draw_icon(icon_name, self.ICON_SIZE, theme.ICON_INK_LIGHT)
        dark = draw_icon(icon_name, self.ICON_SIZE, theme.ICON_INK_DARK)
        if light is None or dark is None:
            return None

        # Kept, because CTkImage builds Tk images of its own and the theme
        # button asks for one on every appearance change - twenty flips made
        # twenty images where two will do. Per instance rather than per
        # class: a CTkImage belongs to the interpreter that made it, and the
        # tests build several.
        image = ctk.CTkImage(light_image=light, dark_image=dark,
                             size=(self.ICON_SIZE, self.ICON_SIZE))
        self._icon_images[icon_name] = image
        return image

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
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="left", padx=1, pady=2)

        image = self._icon_image(icon_name)
        if image is None:
            logger.debug("No drawing for the %s icon; showing its initial",
                         icon_name)

        btn = ctk.CTkButton(
            btn_frame,
            text="" if image is not None else icon_name[:1].upper(),
            image=image,
            width=self.BUTTON_SIZE,
            height=self.BUTTON_SIZE,
            fg_color="transparent",
            hover_color=WIN_MENU_HOVER,
            text_color=WIN_MENU_TEXT,
            corner_radius=4,
            command=command,
        )

        btn.pack(side="left", padx=2, pady=2)
        # Kept from the garbage collector: a CTkImage that is collected
        # takes the picture off the button with it
        btn.icon_image = image
        btn.tooltip = tooltip
        # And the caption said out loud. It was stored on the button and
        # never shown, which made the row readable only to whoever drew it
        btn.tooltip_widget = attach_tooltip(btn, tooltip)

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
    

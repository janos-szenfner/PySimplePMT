"""
The ribbon: a tab strip over grouped commands, with a File backstage.

DEVELOPMENT NOTES:
------------------
This replaced the two stacked rows the window used to open with - a text
menu bar and, under it, a long row of icon buttons. What it replaces them
with is the arrangement LibreOffice and Microsoft Project use: a strip of
tabs along the top, and under it a band of captioned groups, each group
holding the handful of commands that belong together. The group caption is
the difference that matters - the icon row could only be read by hovering
every button in turn, and a caption under the group says what the buttons
are for before the pointer arrives.

Everything here is wiring, not behaviour. A ribbon button names an action,
and the action is looked up on this object the same way the icon row's
were - Toolbar connects the handlers through _connect_icon_toolbar after
construction, so pressing "Set Baseline..." runs exactly what the old menu
entry ran. The formatting bar, the progress group, the search box and the
day/night control are the same widgets the icon row carried, mounted into
the groups they belong to through _mount().

The File tab is not a page of groups but the backstage panel - the
full-window view MS Project opens for file operations, because those are
things done to the plan rather than to whatever is selected in it.
"""

import logging
import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from gantt_app.views import theme
from gantt_app.views.tooltip import attach as attach_tooltip
from gantt_app.views.toolbar import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_TEXT,
    CTkDropdownMenu,
    IconToolbar,
    WIN_MENU_BG,
    WIN_MENU_HOVER,
    WIN_MENU_TEXT,
)

logger = logging.getLogger(__name__)


def _L(icon: str, label: str, action: str, tip: str = None,
       check: str = None, gallery: str = None, key: str = None) -> Dict:
    """One large button: icon over a caption, a column to itself."""
    return {'kind': 'large', 'icon': icon, 'label': label, 'action': action,
            'tip': tip or label, 'check': check, 'gallery': gallery,
            'key': key or icon}


def _S(icon: str, label: str, action: str, tip: str = None,
       check: str = None, gallery: str = None, key: str = None) -> Dict:
    """One small button: icon beside a label, stacked with the others."""
    spec = _L(icon, label, action, tip, check, gallery, key)
    spec['kind'] = 'small'
    return spec


def _SPLIT(icon: str, label: str, action: str,
           items: List[tuple], tip: str = None) -> Dict:
    """A large button with a drop-down half, for the action with variants."""
    return {'kind': 'split', 'icon': icon, 'label': label, 'action': action,
            'tip': tip or label, 'items': items, 'key': icon}


class RibbonGroup(ctk.CTkFrame):
    """
    One captioned group on a ribbon page.

    The caption under the buttons is what makes this a ribbon group rather
    than a stretch of toolbar: "Clipboard" under the paste button is how the
    reader learns the arrangement without hovering. The body holds the
    buttons; the caption holds the name.
    """

    def __init__(self, master, caption: str, **kwargs):
        super().__init__(master, fg_color=WIN_MENU_BG, corner_radius=4,
                         border_width=1,
                         border_color=theme.SEPARATOR, **kwargs)
        self.caption = caption
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(side="top", fill="both", expand=True,
                       padx=4, pady=(4, 0))
        ctk.CTkLabel(
            self, text=caption, text_color=theme.MUTED_TEXT,
            font=ctk.CTkFont(size=10),
        ).pack(side="bottom", pady=(0, 2))


class RibbonBar(IconToolbar):
    """
    The tabbed command band at the top of the window.

    An IconToolbar still - the icon drawing, the button-state logic, the
    formatting and progress groups and the handlers Toolbar connects are
    all inherited. What changes is _create_ui: instead of one long row the
    commands stand in captioned groups on tabbed pages, and the strip above
    them carries what the menu row used to - File, the tabs, and at the
    right the help, appearance and search controls.
    """

    #: The strip and the band's heights, in pixels. The band is tall
    #: enough for a large button's icon and caption, its split-button
    #: arrow, and the group's caption under them - at 92 the captions of
    #: the Insert and Analysis groups were clipped by the frame's bottom
    #: edge and a fourth small button dropped out of sight entirely.
    STRIP_HEIGHT = 30
    BAND_HEIGHT = 110

    #: A large button's width, and its icon's size. The large button is the
    #: ribbon's unit - the two or three commands a group is for get one;
    #: the rest stack small beside them.
    LARGE_WIDTH = 64
    LARGE_ICON = 28
    SMALL_HEIGHT = 22

    TABS = ("Task", "View", "Project")
    DEFAULT_TAB = "Task"

    #: The quick-access icons at the left of the strip, next to File:
    #: the three that are worth one click from anywhere, tab or no tab.
    QAT_ACTIONS = (
        ('save', 'Save Project', 'save_project'),
        ('save_as', 'Save Project As...', 'save_project_as'),
        ('undo', 'Undo', 'undo'),
        ('redo', 'Redo', 'redo'),
    )

    #: The pages, their groups, and each group's buttons. A string instead
    #: of a tuple stands the named control in the group - the formatting
    #: bar and the progress group are built by the helpers this class
    #: inherits, mounted where _mount() points.
    RIBBON = (
        ("Task", (
            ("Clipboard", (
                _L('paste', 'Paste', 'paste_tasks'),
                _S('cut', 'Cut', 'cut_tasks'),
                _S('copy', 'Copy', 'copy_tasks'),
            )),
            ("Insert", (
                _SPLIT('task', 'New Task', 'add_task', (
                    ("Task...", 'add_task'),
                    ("Phase...", 'add_phase'),
                    ("Subtask...", 'add_subtask'),
                    ("Milestone...", 'add_milestone'),
                ), tip="Create a task"),
            )),
            ("Tasks", (
                _L('edit', 'Edit Task', 'edit_selected_task',
                   tip="Edit Task..."),
                _S('delete', 'Delete', 'delete_selected'),
            )),
            ("Outline", (
                _S('indent', 'Indent', 'indent_selected',
                   tip="Indent Task"),
                _S('outdent', 'Outdent', 'outdent_selected',
                   tip="Outdent Task"),
                _S('link', 'Link', 'link_selected', tip="Link Tasks  (F2)"),
                _S('unlink', 'Unlink', 'unlink_selected',
                   tip="Unlink Tasks  (Shift+F2)"),
            )),
            ("Font", 'style_bar'),
            ("Progress", 'progress_group'),
        )),
        ("View", (
            ("Views", (
                _L('gantt', 'Gantt Chart', 'show_gantt_chart'),
                _S('dashboard', 'Dashboard', 'show_dashboard'),
                _S('grid', 'Grid Only', 'toggle_grid_view_only',
                   tip="Grid View Only", check='grid_view_only'),
            )),
            # Shown only while the footer's Resource Planning tab is on
            # top - see CONTEXT_GROUPS. It sits beside Views because it
            # switches what that tab's view is.
            ("Resources", (
                _L('resource_grid', 'Usage Grid', 'toggle_resource_grid',
                   tip="Resource usage grid - the pool as a tree of "
                       "assigned tasks",
                   check='resource_grid', key='resource_grid'),
            )),
            ("Analysis", (
                _L('critical_path', 'Critical', 'toggle_critical_path_rows',
                   tip="Highlight the Critical Path",
                   check='critical_path'),
                _S('critical_path', 'Report...', 'show_critical_path',
                   tip="Critical Path...", key='critical_path_report'),
            )),
            ("Highlight", (
                _L('highlight', 'Highlight', '', gallery='highlight',
                   tip="Paint the rows a filter matches",
                   check='highlight', key='highlight'),
            )),
            ("Filter", (
                _L('filter', 'Filter', 'open_grid_filter',
                   gallery='grid_filter',
                   tip="Show only the rows the columns' rules pass",
                   check='grid_filter', key='grid_filter'),
                _S('clear_style', 'Clear', 'clear_grid_filter',
                   tip="Clear every column filter", key='grid_filter_clear'),
            )),
            ("Appearance", (
                _S('moon', 'Day / Night', '_toggle_theme',
                   tip="Switch between Day and Night",
                   key='appearance_toggle'),
                _S('sync', 'Sync', '_sync_theme',
                   tip="Sync with the System", key='appearance_sync'),
            )),
            ("Window", (
                _L('log', 'Event Log', 'show_log', tip="Log"),
            )),
        )),
        ("Project", (
            ("Properties", (
                _L('settings', 'Settings', 'open_settings',
                   tip="Project Settings..."),
            )),
            ("Baseline", (
                _S('baseline', 'Set...', 'set_baseline',
                   tip="Set Baseline...", key='baseline_set'),
                _S('baseline', 'Clear...', 'clear_baseline',
                   tip="Clear Baseline...", key='baseline_clear'),
                _S('baseline', 'Compare', '',
                   tip="Compare Baseline", gallery='compare',
                   key='baseline_compare'),
            )),
            ("Calendar", (
                _L('calendar', 'Working Week', 'edit_holidays',
                   tip="Working Week & Holidays..."),
            )),
            ("Resources", (
                _L('resource', 'Resources', 'open_resource_settings',
                   tip="Resource Settings..."),
            )),
            ("Leveling", (
                _L('level', 'Level...', 'preview_leveling',
                   tip="Preview resource levelling - what would move "
                       "before anything does",
                   key='leveling_preview'),
                _S('level', 'Level All', 'level_all',
                   tip="Level every overallocated resource now",
                   key='leveling_all'),
            )),
        )),
    )

    #: The backstage's sections. An entry is (icon, label, action); a
    #: 'gallery' instead of an action opens the named gallery, and a
    #: 'provider' instead of entries builds them when the panel opens -
    #: the recent-files list is different every time it is read.
    BACKSTAGE = (
        ("Project", (
            {'icon': 'new_project', 'label': "New Project...",
             'action': 'new_project'},
            {'icon': 'open', 'label': "Open Project...",
             'action': 'load_project'},
            {'icon': 'save', 'label': "Save", 'action': 'save_project'},
            {'icon': 'save_as', 'label': "Save As...",
             'action': 'save_project_as'},
            {'icon': None, 'label': "Close Project",
             'action': 'close_project'},
        )),
        ("Share", (
            {'icon': 'import_icon', 'label': "Import",
             'gallery': 'import'},
            {'icon': 'export_icon', 'label': "Export",
             'gallery': 'export'},
        )),
        ("Recent", 'recent'),
        ("Options", (
            {'icon': 'settings', 'label': "Project Settings...",
             'action': 'open_settings'},
        )),
        ("Info", (
            {'icon': 'help', 'label': "User Guide", 'action': 'show_help'},
            {'icon': None, 'label': "About PySimplePMT",
             'action': 'show_about'},
            {'icon': None, 'label': "Changelog", 'action': 'show_changelog'},
        )),
    )

    #: The actions the ribbon's buttons name beyond the ones ICON_ACTIONS
    #: already lists. Toolbar's _connect_icon_toolbar reads both lists, so
    #: every button here reaches the same handler the menus used to reach.
    EXTRA_ACTIONS = (
        'new_project', 'load_project', 'close_project',
        'add_task', 'add_phase', 'add_subtask', 'add_milestone',
        'open_settings', 'edit_holidays', 'open_resource_settings',
        'set_baseline', 'clear_baseline',
        'show_gantt_chart', 'show_dashboard', 'toggle_grid_view_only',
        'show_critical_path', 'show_log', 'show_about', 'show_changelog',
        'show_help', 'open_grid_filter', 'clear_grid_filter',
        'toggle_resource_grid', 'preview_leveling', 'level_all',
    )

    #: Groups that belong to one footer-tab view and stay hidden while any
    #: other is on top, keyed (ribbon tab, group caption) -> the view's
    #: name in the footer tab bar. set_view_context shows and hides them.
    CONTEXT_GROUPS = {
        ("View", "Resources"): "Resource Planning",
    }

    def __init__(self, master, project, galleries: Dict = None, **kwargs):
        #: Where the inherited helpers place what they build; None is the
        #: ribbon itself. A group sets this to its body while the helper
        #: for the control it holds runs - see _build_group.
        self._mount_point = None
        #: Groups carry their own borders; the row dividers the icon
        #: toolbar draws between its buttons have no place here.
        self._suppress_separators = True
        #: Item lists for the galleries, keyed by name - a list is shown
        #: as given, a callable is asked when the gallery opens. Toolbar
        #: supplies these; see _ribbon_galleries.
        self.galleries = dict(galleries or {})
        self._pages = {}
        self._tab_buttons = {}
        self._groups = {}
        self._check_buttons = []
        self._collapsed = False
        self._active_tab = self.DEFAULT_TAB
        self._backstage = None
        self._open_dropdown = None
        #: Context groups currently off the page, by (tab, caption).
        self._context_hidden = set()
        super().__init__(master, project, **kwargs)
        self.configure(height=self.STRIP_HEIGHT + self.BAND_HEIGHT)

    @staticmethod
    def _collect_action_labels() -> Dict[str, str]:
        """
        The captions _perform logs, for the ribbon's buttons as well as
        the icon row's.

        The ribbon's actions live in RIBBON and BACKSTAGE rather than
        ICON_ACTIONS, so a press logged by name alone would read as
        "close_project" in the Log window where the button said "Close
        Project". Split-button entries name their own actions, so a
        "Phase..." press says Phase rather than New Task.
        """
        labels = IconToolbar._collect_action_labels()
        for _icon, tooltip, action in RibbonBar.QAT_ACTIONS:
            labels[action] = tooltip
        for _tab, groups in RibbonBar.RIBBON:
            for _caption, contents in groups:
                if isinstance(contents, str):
                    continue
                for spec in contents:
                    if spec.get('action'):
                        labels[spec['action']] = spec['label']
                    for item_label, item_action in spec.get('items', ()):
                        labels[item_action] = item_label
        for _section, entries in RibbonBar.BACKSTAGE:
            if isinstance(entries, str):
                continue
            for entry in entries:
                if entry.get('action'):
                    labels[entry['action']] = entry['label']
        return labels

    # ---- construction ----------------------------------------------------

    def _create_ui(self):
        """Build the tab strip, then the band of pages under it."""
        self._create_strip()
        self._create_band()
        self.select_tab(self.DEFAULT_TAB)

    def _create_strip(self):
        """
        File, the quick-access icons, the tabs - and help, theme, search.

        The strip is the menu row's successor: what is reachable no matter
        which page is showing lives here. The right-hand controls are the
        same three the icon row kept at its right edge, built by the same
        helper, mounted into this strip.
        """
        strip = ctk.CTkFrame(self, fg_color=WIN_MENU_BG, corner_radius=0,
                             height=self.STRIP_HEIGHT)
        strip.pack(side="top", fill="x")
        strip.pack_propagate(False)
        self._strip = strip

        self.file_button = ctk.CTkButton(
            strip, text="File", width=54, height=self.STRIP_HEIGHT - 8,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT, corner_radius=4,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_backstage,
        )
        self.file_button.pack(side="left", padx=(5, 3), pady=4)
        self.file_button.tooltip = "File"
        self.file_button.tooltip_widget = attach_tooltip(
            self.file_button, "File - New, Open, Save, Import, Export")

        qat = ctk.CTkFrame(strip, fg_color="transparent")
        qat.pack(side="left", padx=(0, 6))
        self._mount_point = qat
        for icon_name, tip, action in self.QAT_ACTIONS:
            self._create_icon_button(
                icon_name, tip,
                lambda name=action: self._perform(name))
        self._mount_point = None

        tabs = ctk.CTkFrame(strip, fg_color="transparent")
        tabs.pack(side="left")
        for name in self.TABS:
            btn = ctk.CTkButton(
                tabs, text=name, width=64, height=self.STRIP_HEIGHT - 8,
                fg_color="transparent", hover_color=WIN_MENU_HOVER,
                text_color=WIN_MENU_TEXT, corner_radius=4,
                font=ctk.CTkFont(size=12),
                command=lambda n=name: self._tab_pressed(n))
            btn.pack(side="left", padx=1)
            # The ribbon folds on a double-click of a tab, the way both
            # applications it follows fold on one.
            btn.bind("<Double-Button-1>", lambda _e: self.toggle_collapsed())
            self._tab_buttons[name] = btn

        # The fold control is the rightmost thing in the strip; the
        # controls that live at the right edge sit to its left.
        self._collapse_button = ctk.CTkButton(
            strip, text="⌃", width=26, height=self.STRIP_HEIGHT - 10,
            fg_color="transparent", hover_color=WIN_MENU_HOVER,
            text_color=theme.MUTED_TEXT, corner_radius=4,
            command=self.toggle_collapsed)
        self._collapse_button.pack(side="right", padx=(2, 5), pady=3)
        self._collapse_button.tooltip_widget = attach_tooltip(
            self._collapse_button, "Collapse the ribbon")

        #: The right-edge cluster: help, the day/night control and the
        #: search box, held in a frame of their own so they read as the
        #: strip's right end rather than as more tabs.
        self._strip_right = ctk.CTkFrame(strip, fg_color="transparent")
        self._strip_right.pack(side="right")
        self._mount_point = self._strip_right
        self._create_right_hand_controls()
        self._mount_point = None

    def _create_band(self):
        """One page of captioned groups per tab; only the active one packs."""
        self._band = ctk.CTkFrame(self, fg_color=WIN_MENU_BG, corner_radius=0,
                                  height=self.BAND_HEIGHT)
        self._band.pack(side="top", fill="x")
        self._band.pack_propagate(False)
        self._pages.clear()
        self._groups.clear()
        for tab_name, groups in self.RIBBON:
            page = ctk.CTkFrame(self._band, fg_color="transparent")
            for caption, contents in groups:
                group = self._build_group(page, caption, contents)
                self._groups[(tab_name, caption)] = group
            self._pages[tab_name] = page
        for key in self.CONTEXT_GROUPS:
            self.set_group_visible(*key, visible=False)

    def _build_group(self, page, caption: str, contents):
        """
        One group on a page: its buttons, or the control the caption names.

        The formatting bar and the progress group are not buttons but whole
        controls, built by the helpers the icon row used - they are mounted
        into the group's body by pointing _mount() at it while the helper
        runs, which is all _mount() is for.
        """
        group = RibbonGroup(page, caption)
        group.pack(side="left", fill="y", padx=3, pady=3)

        if contents in ('style_bar', 'progress_group'):
            self._mount_point = group.body
            if contents == 'style_bar':
                self._create_style_bar()
            else:
                self._create_progress_group()
            self._mount_point = None
            return group

        column = None
        column_count = 0
        for spec in contents:
            if spec['kind'] in ('large', 'split'):
                column = None
                column_count = 0
                self._large_button(group.body, spec)
            else:
                # The small buttons stack three to a column, like the
                # compact half of every group in the ribbons this follows.
                # A fourth would overflow the group - the band is not tall
                # enough for it - so it starts a new column instead.
                if column is None or column_count >= 3:
                    column = ctk.CTkFrame(group.body, fg_color="transparent")
                    column.pack(side="left", fill="y")
                    column_count = 0
                self._small_button(column, spec)
                column_count += 1
        return group

    # ---- buttons ---------------------------------------------------------

    def _large_button(self, parent, spec: Dict):
        """The group's principal command: a tall button, icon over caption."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(side="left", fill="y", padx=1)

        image = self._icon_image_sized(spec['icon'], self.LARGE_ICON)
        command = self._command_for(spec)
        btn = ctk.CTkButton(
            frame, text=spec['label'], image=image, compound="top",
            width=self.LARGE_WIDTH,
            fg_color="transparent", hover_color=WIN_MENU_HOVER,
            text_color=WIN_MENU_TEXT, corner_radius=4,
            font=ctk.CTkFont(size=11),
            command=command)
        height = self.BAND_HEIGHT - 34
        if spec['kind'] == 'split':
            height -= 16
        btn.configure(height=height)
        btn.pack(side="top", fill="both", expand=True)
        self._dress_button(btn, spec, image)

        if spec['kind'] == 'split':
            arrow = ctk.CTkButton(
                frame, text="▾", height=15,
                fg_color="transparent", hover_color=WIN_MENU_HOVER,
                text_color=WIN_MENU_TEXT, corner_radius=4,
                font=ctk.CTkFont(size=10),
                command=lambda s=spec, f=frame: self._open_gallery(
                    f, self._split_items(s), s['label']))
            arrow.pack(side="bottom", fill="x")
            arrow.tooltip_widget = attach_tooltip(
                arrow, f"{spec['label']} - more")
            #: The drop-down half, kept on the button so a press can be
            #: aimed at it - by a reader, or by a test.
            btn.split_arrow = arrow
        return btn

    def _small_button(self, parent, spec: Dict):
        """A stacked command: small icon beside its label."""
        image = self._icon_image(spec['icon'])
        btn = ctk.CTkButton(
            parent, text=f" {spec['label']}", image=image, compound="left",
            anchor="w", height=self.SMALL_HEIGHT, width=104,
            fg_color="transparent", hover_color=WIN_MENU_HOVER,
            text_color=WIN_MENU_TEXT, corner_radius=4,
            font=ctk.CTkFont(size=11),
            command=self._command_for(spec))
        btn.pack(side="top", fill="x", pady=0)
        self._dress_button(btn, spec, image)
        return btn

    def _dress_button(self, btn, spec: Dict, image):
        """Tooltip, state-tracking and the button registry, for either kind."""
        btn.icon_image = image
        btn.tooltip = spec['tip']
        btn.tooltip_widget = attach_tooltip(btn, spec['tip'])
        # The registry the icon row kept: button state follows whether a
        # project is open, keyed so two buttons sharing an icon name - the
        # two baseline entries, the two critical-path ones - both stand.
        self.icon_buttons[spec['key']] = btn
        if spec.get('check'):
            self._check_buttons.append((btn, spec['check']))

    def _command_for(self, spec: Dict) -> Callable:
        """What a button press runs: the gallery, or the action's handler."""
        if spec.get('gallery'):
            return lambda s=spec: self._gallery_button_pressed(s)
        return lambda a=spec['action']: self._perform(a)

    def _split_items(self, spec: Dict) -> List[Dict]:
        """A split button's drop-down entries, as dropdown-menu items."""
        return [
            {'label': label,
             'command': lambda a=action: self._perform(a)}
            for label, action in spec.get('items', ())
        ]

    def _gallery_button_pressed(self, spec: Dict):
        """Open the named gallery under its own button."""
        provider = self.galleries.get(spec['gallery'])
        items = provider() if callable(provider) else provider
        anchor = self.icon_buttons.get(spec['key'])
        if anchor is not None:
            self._open_gallery(anchor, items or [], spec['label'])

    @staticmethod
    def _logged_items(items: List[Dict], title: Optional[str]
                      ) -> List[Dict]:
        """
        The gallery's entries, each logged under its label when it runs.

        Gallery commands are callables rather than action names, so they
        never reach _perform and would otherwise leave nothing in the log:
        a "MS Project..." pick would be invisible until the importer wrote
        its own line. The label from the button that opened the list is
        prepended, so the log reads "Export: PNG..." rather than a bare
        file extension.
        """
        logged = []
        for item in items:
            item = dict(item)
            command = item.get('command')
            if callable(command):
                label = item.get('label', '')
                entry = f"{title}: {label}" if title else label
                item['command'] = RibbonBar._logged_command(entry, command)
            submenu = item.get('submenu')
            if submenu:
                item['submenu'] = RibbonBar._logged_items(submenu, title)
            logged.append(item)
        return logged

    @staticmethod
    def _logged_command(entry: str, command: Callable) -> Callable:
        """A menu command that writes its own label to the log first."""
        def run():
            logger.info("Menu: %s", entry)
            command()
        return run

    def _open_gallery(self, anchor, items: List[Dict], title: str = None):
        """
        Drop the item list under the widget that asked for it.

        The same CTkDropdownMenu the old menu bar dropped, positioned under
        the button the way CustomMenuBar positioned it under its buttons.
        A second press on the same button closes rather than reopens.
        """
        open_menu = self._open_dropdown
        if open_menu is not None and open_menu.winfo_exists():
            open_menu.destroy()
            self._open_dropdown = None
            if getattr(open_menu, '_ribbon_anchor', None) is anchor:
                return

        if not items:
            return
        menu = CTkDropdownMenu(self.winfo_toplevel(),
                               items=self._logged_items(items, title),
                               opener=anchor)
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 2
        menu.geometry(f"+{x}+{y}")
        menu._ribbon_anchor = anchor
        menu.focus_set()
        self._open_dropdown = menu

    def _icon_image_sized(self, icon_name: str, size: int):
        """One icon at a size the row's cache does not cover."""
        key = (icon_name, size)
        cached = self._icon_images.get(key)
        if cached is not None:
            return cached
        from gantt_app.resources.icons import draw_icon
        light = draw_icon(icon_name, size, theme.ICON_INK_LIGHT)
        dark = draw_icon(icon_name, size, theme.ICON_INK_DARK)
        if light is None or dark is None:
            return None
        image = ctk.CTkImage(light_image=light, dark_image=dark,
                             size=(size, size))
        self._icon_images[key] = image
        return image

    # ---- the helpers this inherits, aimed into groups --------------------

    def _mount(self):
        """Where a helper's controls go: the group body that asked, or self."""
        return self._mount_point if self._mount_point is not None else self

    def _create_separator(self, side: str = "left"):
        """No row dividers here - the groups carry borders of their own."""
        if getattr(self, '_suppress_separators', False):
            return
        super()._create_separator(side)

    def _create_style_bar(self):
        """The formatting controls, alone - the progress group is elsewhere."""
        from gantt_app.views.stylebar import StyleBar

        self.style_bar = StyleBar(
            self._mount(), on_apply=self._style_applied,
            button_size=self.BUTTON_SIZE, icon_image=self._icon_image)
        self.style_bar.pack(side="left", padx=1)

    # ---- tabs and folding --------------------------------------------------

    def _tab_pressed(self, name: str):
        """What a tab click runs: the log entry, then the page change."""
        logger.info("Ribbon tab: %s", name)
        self.select_tab(name)

    def select_tab(self, name: str):
        """Show one page and mark its tab; an unknown name changes nothing."""
        if name not in self._pages:
            return
        self._active_tab = name
        for tab_name, page in self._pages.items():
            if tab_name == name and not self._collapsed:
                page.pack(side="top", fill="both", expand=True)
            else:
                page.pack_forget()
        self._restyle_tabs()

    def set_view_context(self, view_name: str) -> None:
        """
        Show the groups the active footer-tab view lends the ribbon.

        The Resources group on the View page exists only while Resource
        Planning is on top; the other pages' groups are always up.
        """
        for (tab, caption), wanted in self.CONTEXT_GROUPS.items():
            self.set_group_visible(tab, caption, view_name == wanted)
        self.refresh_checks()

    def set_group_visible(self, tab: str, caption: str,
                          visible: bool) -> None:
        """
        Pack or unpack one group on a page, keeping its place in the row.

        A hidden group is pack_forget()'d; shown again it packs after the
        nearest visible group that precedes it in the page's declared
        order, so a context group always reappears where RIBBON put it.
        """
        group = self._groups.get((tab, caption))
        if group is None:
            return
        if not visible:
            if (tab, caption) not in self._context_hidden:
                self._context_hidden.add((tab, caption))
                group.pack_forget()
            return
        self._context_hidden.discard((tab, caption))
        anchor = None
        for name, groups in self.RIBBON:
            if name != tab:
                continue
            for prev_caption, _contents in groups:
                if prev_caption == caption:
                    break
                if (tab, prev_caption) not in self._context_hidden:
                    anchor = self._groups.get((tab, prev_caption))
            break
        options = {'side': 'left', 'fill': 'y', 'padx': 3, 'pady': 3}
        if anchor is not None:
            options['after'] = anchor
        group.pack(**options)

    def _restyle_tabs(self):
        """Draw the active tab apart from the rest."""
        for name, btn in self._tab_buttons.items():
            if name == self._active_tab and not self._collapsed:
                btn.configure(fg_color=WIN_MENU_HOVER)
            else:
                btn.configure(fg_color="transparent")

    def toggle_collapsed(self):
        """Fold the band away to the strip alone, or bring it back."""
        logger.info("Ribbon %s",
                    "expanded" if self._collapsed else "collapsed")
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        """Fold the band away, or show the active page again."""
        self._collapsed = bool(collapsed)
        if self._collapsed:
            for page in self._pages.values():
                page.pack_forget()
            self._band.pack_forget()
            self._collapse_button.configure(text="⌄")
        else:
            self._band.pack(side="top", fill="x", after=self._strip)
            self._collapse_button.configure(text="⌃")
        self._restyle_tabs()
        self.select_tab(self._active_tab)

    # ---- the checked look --------------------------------------------------

    def refresh_checks(self):
        """Repaint the toggle buttons to match the state they stand for."""
        for btn, which in self._check_buttons:
            try:
                pressed = self._is_checked(which)
                btn.configure(
                    fg_color=WIN_MENU_HOVER if pressed else "transparent")
            except (AttributeError, tk.TclError):
                continue

    def _is_checked(self, which: str) -> bool:
        """Whether the state a toggle button stands for is on."""
        if which == 'grid_view_only':
            var = getattr(self, 'grid_view_only_var', None)
            return bool(var is not None and var.get())
        if which == 'resource_grid':
            var = getattr(self, 'resource_grid_var', None)
            return bool(var is not None and var.get())
        if which == 'critical_path':
            task_list = getattr(self, 'task_list', None)
            return bool(task_list is not None
                        and hasattr(task_list, 'critical_path_rows_shown')
                        and task_list.critical_path_rows_shown())
        if which == 'highlight':
            task_list = getattr(self, 'task_list', None)
            return bool(task_list is not None
                        and hasattr(task_list, 'highlighted_rows_shown')
                        and task_list.highlighted_rows_shown())
        if which == 'grid_filter':
            task_list = getattr(self, 'task_list', None)
            return bool(task_list is not None
                        and hasattr(task_list, 'grid_filters_active')
                        and task_list.grid_filters_active())
        return False

    def _perform(self, action: str):
        """Run the handler, then let the toggle buttons catch up with it."""
        super()._perform(action)
        if self._check_buttons:
            self.after_idle(self.refresh_checks)

    # ---- the File backstage --------------------------------------------------

    def toggle_backstage(self):
        """Open the File view, or close the one already open."""
        if self._backstage is not None:
            try:
                if self._backstage.winfo_exists():
                    logger.info("File backstage closed")
                    self._backstage.close()
                    return
            except tk.TclError:
                # The panel is half-destroyed; forget it and open fresh.
                pass
            self._backstage = None

        logger.info("File backstage opened")
        self._backstage = BackstagePanel(self)
        self._backstage.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._backstage.lift()
        self._backstage.focus_set()

    def _backstage_items(self, provider) -> List[Dict]:
        """A backstage section's rows, built when the panel opens."""
        items = provider() if callable(provider) else provider
        return items or []

    def action_names(self) -> List[str]:
        """Every action name a ribbon or backstage button can call."""
        names = [a for _i, _t, a in self.ICON_ACTIONS if a]
        names += list(self.EXTRA_ACTIONS)
        for _tab, groups in self.RIBBON:
            for _caption, contents in groups:
                if isinstance(contents, str):
                    continue
                for spec in contents:
                    if spec.get('action'):
                        names.append(spec['action'])
                    for _label, sub in spec.get('items', ()):
                        names.append(sub)
        for _section, entries in self.BACKSTAGE:
            if isinstance(entries, str):
                continue
            for entry in entries:
                if entry.get('action'):
                    names.append(entry['action'])
        return names


class BackstagePanel(ctk.CTkFrame):
    """
    The File view: a panel over the whole window.

    Not a menu and not a page of groups - file operations are things done
    to the plan rather than to a selection in it, so they get the full
    window, the way MS Project's backstage does. What is in it is the
    ribbon's BACKSTAGE list: a section per column, a row per command, and
    the galleries - import, export, recent - built when the panel opens,
    not when the application does.
    """

    def __init__(self, ribbon: RibbonBar, **kwargs):
        super().__init__(ribbon.winfo_toplevel(),
                         fg_color=WIN_MENU_BG, **kwargs)
        self.ribbon = ribbon

        header = ctk.CTkFrame(self, fg_color="transparent", height=44)
        header.pack(side="top", fill="x", padx=16, pady=(12, 4))
        back = ctk.CTkButton(
            header, text="← Back", width=76, height=30,
            fg_color="transparent", hover_color=WIN_MENU_HOVER,
            text_color=WIN_MENU_TEXT, corner_radius=4,
            command=self.close)
        back.pack(side="left")
        ctk.CTkLabel(
            header, text="File",
            text_color=WIN_MENU_TEXT,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=12)

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(side="top", fill="both", expand=True,
                     padx=16, pady=8)
        self._build_sections(columns)

        self.bind("<Escape>", lambda _e: self.close())

    def _build_sections(self, parent):
        """A column per section, its rows the commands it holds."""
        for section, entries in self.ribbon.BACKSTAGE:
            column = ctk.CTkFrame(parent, fg_color="transparent")
            column.pack(side="left", fill="y", padx=(0, 24))
            ctk.CTkLabel(
                column, text=section, anchor="w",
                text_color=theme.MUTED_TEXT,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(fill="x", pady=(0, 6))

            if isinstance(entries, str):
                # A provider name: the rows are built now, from the list
                # as it stands - the recent files as they are this minute.
                provider = self.ribbon.galleries.get(entries)
                for item in self.ribbon._logged_items(
                        self.ribbon._backstage_items(provider), section):
                    self._row(column, None, item.get('label', ''),
                              item.get('command'))
                continue

            for entry in entries:
                if entry.get('gallery'):
                    self._gallery_row(column, entry)
                else:
                    self._row(
                        column, entry.get('icon'), entry.get('label', ''),
                        lambda a=entry['action']: self._run(a))

    def _row(self, parent, icon, label: str, command: Optional[Callable]):
        """One backstage entry: a wide row, an icon if there is one."""
        image = None
        if icon:
            image = self.ribbon._icon_image(icon)
        btn = ctk.CTkButton(
            parent, text=f"  {label}", image=image, compound="left",
            anchor="w", height=30, width=190,
            fg_color="transparent", hover_color=WIN_MENU_HOVER,
            text_color=WIN_MENU_TEXT, corner_radius=4,
            font=ctk.CTkFont(size=12),
            command=command)
        btn.pack(fill="x", pady=1)
        if image is not None:
            btn.icon_image = image
        return btn

    def _gallery_row(self, parent, entry: Dict):
        """A row whose press drops the named gallery beneath it."""
        btn = self._row(parent, entry.get('icon'),
                        f"{entry.get('label', '')} ▸", None)
        btn.configure(command=lambda b=btn, e=entry: self._open(b, e))

    def _open(self, anchor, entry: Dict):
        """Drop the gallery's items under the row that asked."""
        provider = self.ribbon.galleries.get(entry['gallery'])
        items = provider() if callable(provider) else provider
        self.ribbon._open_gallery(anchor, items or [], entry.get('label'))

    def _run(self, action: str):
        """A backstage command closes the panel, then runs."""
        self.close()
        self.ribbon._perform(action)

    def close(self):
        """Put the panel away and let the window have focus back."""
        if self.ribbon._backstage is self:
            self.ribbon._backstage = None
        self.destroy()

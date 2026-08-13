"""
Gantt Chart Settings Dialog for the Gantt Project Management Tool.

Provides a dialog for customizing Gantt chart appearance settings.
"""

import tkinter as tk
from typing import Optional, Callable, Dict

import customtkinter as ctk


# Mermaid.live themes for chart styling
MERMAID_THEMES = {
    "Default": {
        "bg_color": "#ffffff",
        "task_color": "#1f6aa5",
        "milestone_color": "#e74c3c",
        "dependency_color": "#e74c3c",
        "text_color": "#000000",
        "grid_color": "#ecf0f1"
    },
    "Dark": {
        "bg_color": "#1e1e1e",
        "task_color": "#0078d4",
        "milestone_color": "#ff6b6b",
        "dependency_color": "#ff6b6b",
        "text_color": "#ffffff",
        "grid_color": "#3d3d3d"
    },
    "Forest": {
        "bg_color": "#1a2e2e",
        "task_color": "#2ecc71",
        "milestone_color": "#e74c3c",
        "dependency_color": "#f39c12",
        "text_color": "#ffffff",
        "grid_color": "#2d3d3d"
    },
    "Base": {
        "bg_color": "#f9f9f9",
        "task_color": "#4285f4",
        "milestone_color": "#ea4335",
        "dependency_color": "#34a853",
        "text_color": "#333333",
        "grid_color": "#e0e0e0"
    },
    "Neutral": {
        "bg_color": "#f5f5f5",
        "task_color": "#666666",
        "milestone_color": "#999999",
        "dependency_color": "#cccccc",
        "text_color": "#333333",
        "grid_color": "#e0e0e0"
    }
}


class GanttChartSettingsDialog(ctk.CTkToplevel):
    """
    Dialog for customizing Gantt chart appearance settings.
    Allows users to change font sizes, colors, and themes.
    """
    
    def __init__(self, master, gantt_chart, on_settings_changed=None):
        super().__init__(master)
        
        self.gantt_chart = gantt_chart
        self.on_settings_changed = on_settings_changed
        
        self.title("Gantt Chart Settings")
        self.geometry("500x600")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Store current settings
        self.settings = {
            "font_size": 12,
            "task_color": gantt_chart.task_color,
            "milestone_color": gantt_chart.milestone_color,
            "dependency_color": gantt_chart.dependency_color,
            "theme": "Default",
            "bg_color": "#ffffff",
            "text_color": "#000000",
            "grid_color": "#ecf0f1"
        }
        
        # Create UI
        self._create_ui()
        
        # Center window
        self.center_window()
    
    def _create_ui(self):
        """Create the settings UI."""
        main_frame = ctk.CTkScrollableFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Font Size
        ctk.CTkLabel(main_frame, text="Font Size:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky=tk.W, pady=(10, 5))
        self.font_size_slider = ctk.CTkSlider(main_frame, from_=8, to=24, number_of_steps=16)
        self.font_size_slider.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 15))
        self.font_size_slider.set(self.settings["font_size"])
        self.font_size_label = ctk.CTkLabel(main_frame, text=f"Font Size: {self.settings['font_size']}px")
        self.font_size_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 15))
        self.font_size_slider.bind("<B1-Motion>", self._update_font_label)
        self.font_size_slider.bind("<ButtonRelease-1>", self._update_font_label)
        
        # Theme Selection
        ctk.CTkLabel(main_frame, text="Chart Theme:", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, sticky=tk.W, pady=(10, 5))
        theme_names = list(MERMAID_THEMES.keys())
        self.theme_var = ctk.StringVar(value=self.settings["theme"])
        self.theme_menu = ctk.CTkOptionMenu(
            main_frame, variable=self.theme_var,
            values=theme_names, command=self._update_theme_preview
        )
        self.theme_menu.grid(row=4, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 15))
        
        # Theme Preview
        self.theme_preview = ctk.CTkFrame(main_frame, height=40, corner_radius=5)
        self.theme_preview.grid(row=5, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 15))
        self._update_theme_preview()
        
        # Task Color
        ctk.CTkLabel(main_frame, text="Task Bar Color:", font=ctk.CTkFont(weight="bold")).grid(row=6, column=0, sticky=tk.W, pady=(10, 5))
        self.task_color_entry = ctk.CTkEntry(main_frame)
        self.task_color_entry.grid(row=7, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))
        self.task_color_entry.insert(0, self.settings["task_color"])
        self.task_color_btn = ctk.CTkButton(main_frame, text="Pick Color", command=self._pick_task_color)
        self.task_color_btn.grid(row=8, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 15))
        
        # Milestone Color
        ctk.CTkLabel(main_frame, text="Milestone Color:", font=ctk.CTkFont(weight="bold")).grid(row=9, column=0, sticky=tk.W, pady=(10, 5))
        self.milestone_color_entry = ctk.CTkEntry(main_frame)
        self.milestone_color_entry.grid(row=10, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))
        self.milestone_color_entry.insert(0, self.settings["milestone_color"])
        self.milestone_color_btn = ctk.CTkButton(main_frame, text="Pick Color", command=self._pick_milestone_color)
        self.milestone_color_btn.grid(row=11, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 15))
        
        # Dependency Line Color
        ctk.CTkLabel(main_frame, text="Dependency Line Color:", font=ctk.CTkFont(weight="bold")).grid(row=12, column=0, sticky=tk.W, pady=(10, 5))
        self.dependency_color_entry = ctk.CTkEntry(main_frame)
        self.dependency_color_entry.grid(row=13, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))
        self.dependency_color_entry.insert(0, self.settings["dependency_color"])
        self.dependency_color_btn = ctk.CTkButton(main_frame, text="Pick Color", command=self._pick_dependency_color)
        self.dependency_color_btn.grid(row=14, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 15))
        
        # Background Color
        ctk.CTkLabel(main_frame, text="Background Color:", font=ctk.CTkFont(weight="bold")).grid(row=15, column=0, sticky=tk.W, pady=(10, 5))
        self.bg_color_entry = ctk.CTkEntry(main_frame)
        self.bg_color_entry.grid(row=16, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))
        self.bg_color_entry.insert(0, self.settings["bg_color"])
        self.bg_color_btn = ctk.CTkButton(main_frame, text="Pick Color", command=self._pick_bg_color)
        self.bg_color_btn.grid(row=17, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 15))
        
        # Grid Color
        ctk.CTkLabel(main_frame, text="Grid Color:", font=ctk.CTkFont(weight="bold")).grid(row=18, column=0, sticky=tk.W, pady=(10, 5))
        self.grid_color_entry = ctk.CTkEntry(main_frame)
        self.grid_color_entry.grid(row=19, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))
        self.grid_color_entry.insert(0, self.settings["grid_color"])
        self.grid_color_btn = ctk.CTkButton(main_frame, text="Pick Color", command=self._pick_grid_color)
        self.grid_color_btn.grid(row=20, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 15))
        
        # Buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkButton(button_frame, text="Apply", command=self.apply).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(button_frame, text="Reset to Default", command=self.reset_to_default).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        
        # Configure grid
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def _update_font_label(self, event=None):
        """Update font size label."""
        size = int(self.font_size_slider.get())
        self.font_size_label.configure(text=f"Font Size: {size}px")
        self.settings["font_size"] = size
    
    def _update_theme_preview(self, event=None):
        """Update theme preview color."""
        theme_name = self.theme_var.get()
        theme = MERMAID_THEMES.get(theme_name, MERMAID_THEMES["Default"])
        self.theme_preview.configure(fg_color=theme["bg_color"])
        
        # Update all settings from theme
        for key, value in theme.items():
            self.settings[key] = value
        
        # Update entry fields to match theme
        self.task_color_entry.delete(0, tk.END)
        self.task_color_entry.insert(0, theme["task_color"])
        self.milestone_color_entry.delete(0, tk.END)
        self.milestone_color_entry.insert(0, theme["milestone_color"])
        self.dependency_color_entry.delete(0, tk.END)
        self.dependency_color_entry.insert(0, theme["dependency_color"])
        self.bg_color_entry.delete(0, tk.END)
        self.bg_color_entry.insert(0, theme["bg_color"])
        self.grid_color_entry.delete(0, tk.END)
        self.grid_color_entry.insert(0, theme["grid_color"])
    
    def _pick_task_color(self):
        """Open color picker for task color."""
        color = self._pick_color(self.task_color_entry.get())
        if color:
            self.task_color_entry.delete(0, tk.END)
            self.task_color_entry.insert(0, color)
            self.settings["task_color"] = color
    
    def _pick_milestone_color(self):
        """Open color picker for milestone color."""
        color = self._pick_color(self.milestone_color_entry.get())
        if color:
            self.milestone_color_entry.delete(0, tk.END)
            self.milestone_color_entry.insert(0, color)
            self.settings["milestone_color"] = color
    
    def _pick_dependency_color(self):
        """Open color picker for dependency color."""
        color = self._pick_color(self.dependency_color_entry.get())
        if color:
            self.dependency_color_entry.delete(0, tk.END)
            self.dependency_color_entry.insert(0, color)
            self.settings["dependency_color"] = color
    
    def _pick_bg_color(self):
        """Open color picker for background color."""
        color = self._pick_color(self.bg_color_entry.get())
        if color:
            self.bg_color_entry.delete(0, tk.END)
            self.bg_color_entry.insert(0, color)
            self.settings["bg_color"] = color
            self.theme_preview.configure(fg_color=color)
    
    def _pick_grid_color(self):
        """Open color picker for grid color."""
        color = self._pick_color(self.grid_color_entry.get())
        if color:
            self.grid_color_entry.delete(0, tk.END)
            self.grid_color_entry.insert(0, color)
            self.settings["grid_color"] = color
    
    def _pick_color(self, current_color):
        """Open a color picker dialog."""
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="Select Color", initialcolor=current_color)[1]
        return color
    
    def apply(self):
        """Apply the settings to the chart."""
        # Get all current values from entries
        self.settings["font_size"] = int(self.font_size_slider.get())
        self.settings["task_color"] = self.task_color_entry.get()
        self.settings["milestone_color"] = self.milestone_color_entry.get()
        self.settings["dependency_color"] = self.dependency_color_entry.get()
        self.settings["bg_color"] = self.bg_color_entry.get()
        self.settings["grid_color"] = self.grid_color_entry.get()
        self.settings["theme"] = self.theme_var.get()
        
        # Update gantt chart settings
        self.gantt_chart.task_color = self.settings["task_color"]
        self.gantt_chart.milestone_color = self.settings["milestone_color"]
        self.gantt_chart.dependency_color = self.settings["dependency_color"]
        
        # Store settings for persistence (could save to config file)
        self.gantt_chart.chart_settings = self.settings.copy()
        
        # Redraw chart with new settings
        self.gantt_chart.draw_chart()
        
        # Call callback if provided
        if self.on_settings_changed:
            self.on_settings_changed(self.settings)
        
        self.destroy()
    
    def reset_to_default(self):
        """Reset all settings to default values."""
        default_theme = MERMAID_THEMES["Default"]
        self.settings.update(default_theme)
        self.settings["font_size"] = 12
        self.settings["theme"] = "Default"
        
        # Update UI
        self.font_size_slider.set(12)
        self.font_size_label.configure(text="Font Size: 12px")
        self.theme_var.set("Default")
        self._update_theme_preview()
    
    def cancel(self):
        """Cancel without applying changes."""
        self.destroy()
    
    def center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

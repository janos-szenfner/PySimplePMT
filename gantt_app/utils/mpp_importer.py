"""
MPP file importer for the Gantt Project Management Tool.

Imports Microsoft Project (.mpp) files using Tasklib.

DEVELOPMENT NOTES:
------------------
Tasklib is a pure Python reader and stays an optional dependency: it is not
bundled into the packaged build, and its absence disables MPP import without
affecting anything else.

A JPype + mpxj backend was removed. It was a Java bridge rather than a Python
solution - it needed a JVM and a separately downloaded mpxj.jar on the user's
machine, which cannot be shipped inside a self-contained package and put an
external runtime back onto the end user.
"""

import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from gantt_app.models import Project, Task
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


class MPPImporter:
    """
    Base class for MPP file import.
    
    Provides a unified interface for different MPP import methods.
    """
    
    def import_mpp(self, filepath: str) -> Optional[Project]:
        """
        Import a .mpp file and convert it to a Project object.
        
        This method should be implemented by subclasses.
        """
        raise NotImplementedError("MPP import method not implemented")


class TasklibMPPImporter(MPPImporter):
    """
    Imports MPP files using Tasklib library.
    
    Tasklib is a pure Python library for reading MS Project files.
    Install with: pip install tasklib
    """
    
    def __init__(self):
        self.tasklib_available = False
        try:
            import tasklib
            self.tasklib = tasklib
            self.tasklib_available = True
        except ImportError:
            # An absent optional dependency is expected, not a fault: log it
            # at info level and without a traceback, so the Log window's
            # error count and Error filter stay meaningful
            logger.info(
                "Tasklib not installed; MPP import disabled "
                "(enable with: pip install tasklib)"
            )
    
    def import_mpp(self, filepath: str) -> Optional[Project]:
        """
        Import MPP file using Tasklib.
        """
        if not self.tasklib_available:
            logger.warning("Tasklib is not available for MPP import")
            return None
        
        try:
            if not Path(filepath).exists():
                logger.warning(f"File not found: {filepath}")
                return None
            
            # Open MPP file with Tasklib
            project_file = self.tasklib.ProjectFile(filepath)
            
            # Get project name
            project_name = getattr(project_file, 'name', 'Imported MPP Project')
            
            # Parse tasks
            tasks = self._parse_tasklib_tasks(project_file)
            
            # Create Project
            project = Project(name=project_name, tasks=tasks)
            
            return project
            
        except Exception as e:
            logger.exception(f"Error importing MPP file with Tasklib: {e}")
            return None
    
    def _parse_tasklib_tasks(self, project_file) -> List[Task]:
        """
        Parse tasks from Tasklib project file.
        """
        tasks = []
        
        # Get all tasks from Tasklib
        tasklib_tasks = getattr(project_file, 'tasks', [])
        
        for tasklib_task in tasklib_tasks:
            task = self._parse_tasklib_task(tasklib_task)
            if task:
                tasks.append(task)
        
        return tasks
    
    def _parse_tasklib_task(self, tasklib_task) -> Optional[Task]:
        """
        Parse a single task from Tasklib.
        """
        try:
            # Get task properties
            task_id = str(getattr(tasklib_task, 'id', str(uuid.uuid4())))
            name = getattr(tasklib_task, 'name', 'Unnamed Task')
            
            # Get dates
            start_date = self._parse_tasklib_date(getattr(tasklib_task, 'start', None))
            end_date = self._parse_tasklib_date(getattr(tasklib_task, 'finish', None))
            
            # Check if this is a milestone (duration = 0)
            duration = getattr(tasklib_task, 'duration', None)
            is_milestone = duration is not None and duration.total_seconds() == 0
            
            if is_milestone:
                end_date = None
            
            # Get progress
            percent_complete = getattr(tasklib_task, 'percent_complete', 0)
            progress = int(percent_complete) if percent_complete is not None else 0
            
            # Get dependencies
            dependencies = []
            predecessors = getattr(tasklib_task, 'predecessors', [])
            for pred in predecessors:
                pred_id = getattr(pred, 'task_id', None)
                if pred_id:
                    dependencies.append(str(pred_id))
            
            # Create Task object
            task = Task(
                id=task_id,
                name=name,
                start_date=start_date or datetime.now(),
                end_date=end_date,
                progress=progress,
                dependencies=dependencies,
                color='#1f6aa5',
                is_milestone=is_milestone
            )
            
            return task
            
        except Exception as e:
            logger.exception(f"Error parsing Tasklib task: {e}")
            return None
    
    def _parse_tasklib_date(self, date_obj) -> Optional[datetime]:
        """
        Parse date from Tasklib (could be datetime or None).
        """
        if date_obj is None:
            return None
        if isinstance(date_obj, datetime):
            return date_obj
        try:
            return datetime.fromisoformat(str(date_obj))
        except (ValueError, TypeError):
            return None


class MPPImportManager:
    """
    Manages MPP import methods, trying each available approach in turn.
    """

    def __init__(self):
        self.importers = []

        # Try to initialize Tasklib importer
        tasklib_importer = TasklibMPPImporter()
        if tasklib_importer.tasklib_available:
            self.importers.append(tasklib_importer)

    def import_mpp(self, filepath: str) -> Optional[Project]:
        """
        Import MPP file using the first available importer.
        """
        for importer in self.importers:
            try:
                project = importer.import_mpp(filepath)
                if project:
                    return project
            except Exception as e:
                logger.exception(f"Importer {importer.__class__.__name__} failed: {e}")
                continue

        logger.warning(
            "MPP import is unavailable. Install the optional reader with: "
            "pip install tasklib"
        )
        return None


# Convenience functions
def import_mpp_file(filepath: str) -> Optional[Project]:
    """Import a .mpp file using the best available method."""
    manager = MPPImportManager()
    return manager.import_mpp(filepath)


# Handle import for uuid
import uuid

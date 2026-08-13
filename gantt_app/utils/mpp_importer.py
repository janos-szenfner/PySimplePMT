"""
MPP file importer for the Gantt Project Management Tool.

Imports Microsoft Project (.mpp) files using Tasklib or JPype + mpxj.
"""

import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from gantt_app.models import Project, Task


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
            print("Tasklib not available. Install with: pip install tasklib")
    
    def import_mpp(self, filepath: str) -> Optional[Project]:
        """
        Import MPP file using Tasklib.
        """
        if not self.tasklib_available:
            print("Tasklib is not available for MPP import")
            return None
        
        try:
            if not Path(filepath).exists():
                print(f"File not found: {filepath}")
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
            print(f"Error importing MPP file with Tasklib: {e}")
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
            print(f"Error parsing Tasklib task: {e}")
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


class JPypeMPPImporter(MPPImporter):
    """
    Imports MPP files using JPype + mpxj (Java bridge).
    
    Requires Java JDK 8+ and mpxj library.
    Install with: pip install JPype1
    Download mpxj: https://mpxj.sourceforge.io/
    """
    
    def __init__(self):
        self.jpype_available = False
        try:
            import jpype
            import jpype.imports
            self.jpype = jpype
            self.jpype_available = True
        except ImportError:
            print("JPype not available. Install with: pip install JPype1")
    
    def import_mpp(self, filepath: str) -> Optional[Project]:
        """
        Import MPP file using JPype + mpxj.
        """
        if not self.jpype_available:
            print("JPype is not available for MPP import")
            return None
        
        try:
            # Check if JVM is started
            if not self.jpype.isJVMStarted():
                # Start JVM - this may fail if Java is not installed
                self.jpype.startJVM(classpath=['mpxj.jar'])  # User needs to have mpxj.jar
            
            # Import Java classes
            from java.io import File
            from net.sf.mpxj import ProjectFile
            from net.sf.mpxj.reader import UniversalProjectReader
            
            # Read MPP file
            mpp_file = File(filepath)
            reader = UniversalProjectReader()
            project_file = reader.read(mpp_file)
            
            # Get project name
            project_name = str(project_file.getProjectProperties().getProjectTitle())
            
            # Parse tasks
            tasks = self._parse_mpxj_tasks(project_file)
            
            # Create Project
            project = Project(name=project_name, tasks=tasks)
            
            return project
            
        except Exception as e:
            print(f"Error importing MPP file with JPype/mpxj: {e}")
            return None
    
    def _parse_mpxj_tasks(self, project_file) -> List[Task]:
        """
        Parse tasks from mpxj ProjectFile.
        """
        tasks = []
        
        try:
            # Get all tasks
            mpxj_tasks = project_file.getTasks()
            
            while mpxj_tasks.hasNext():
                mpxj_task = mpxj_tasks.next()
                task = self._parse_mpxj_task(mpxj_task)
                if task:
                    tasks.append(task)
            
        except Exception as e:
            print(f"Error parsing mpxj tasks: {e}")
        
        return tasks
    
    def _parse_mpxj_task(self, mpxj_task) -> Optional[Task]:
        """
        Parse a single task from mpxj.
        """
        try:
            # Get task properties
            task_id = str(mpxj_task.getID())
            name = str(mpxj_task.getName())
            
            # Get dates
            start_date = self._parse_java_date(mpxj_task.getStart())
            end_date = self._parse_java_date(mpxj_task.getFinish())
            
            # Check if this is a milestone
            duration = mpxj_task.getDuration()
            is_milestone = duration is not None and duration.getDuration() == 0
            
            if is_milestone:
                end_date = None
            
            # Get progress
            percent_complete = mpxj_task.getPercentComplete()
            progress = int(percent_complete) if percent_complete is not None else 0
            
            # Get dependencies
            dependencies = []
            predecessors = mpxj_task.getPredecessors()
            while predecessors.hasNext():
                pred = predecessors.next()
                pred_id = str(pred.getSourceTask().getID())
                dependencies.append(pred_id)
            
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
            print(f"Error parsing mpxj task: {e}")
            return None
    
    def _parse_java_date(self, java_date) -> Optional[datetime]:
        """
        Parse Java Date object to Python datetime.
        """
        if java_date is None:
            return None
        try:
            # Convert Java Date to Python datetime
            timestamp = java_date.getTime()
            return datetime.fromtimestamp(timestamp / 1000)
        except Exception:
            return None


class MPPImportManager:
    """
    Manages MPP import methods, trying different approaches.
    """
    
    def __init__(self):
        self.importers = []
        
        # Try to initialize Tasklib importer
        tasklib_importer = TasklibMPPImporter()
        if tasklib_importer.tasklib_available:
            self.importers.append(tasklib_importer)
        
        # Try to initialize JPype importer
        jpype_importer = JPypeMPPImporter()
        if jpype_importer.jpype_available:
            self.importers.append(jpype_importer)
    
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
                print(f"Importer {importer.__class__.__name__} failed: {e}")
                continue
        
        print("No MPP importer available. Install Tasklib or JPype + mpxj.")
        return None


# Convenience functions
def import_mpp_file(filepath: str) -> Optional[Project]:
    """Import a .mpp file using the best available method."""
    manager = MPPImportManager()
    return manager.import_mpp(filepath)


# Handle import for uuid
import uuid

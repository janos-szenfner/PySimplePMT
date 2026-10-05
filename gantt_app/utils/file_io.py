"""
File I/O utilities for the Gantt Project Management Tool.

Handles JSON serialization and deserialization of Project objects.
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from gantt_app.core.models import Project
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


def atomic_write(filepath: str, write, keep_backup: bool = True) -> Path:
    """
    Write a file through a temporary sibling, then swap it into place.

    PARAMETERS:
    -----------
    filepath : str
        The file the content is meant for.
    write : callable
        Given the temporary path; produces the content there.
    keep_backup : bool, optional
        Rename an existing file to <name>.bak first. True by default -
        a failed or half-liked write then never loses what was there.

    RETURNS:
    --------
    Path
        The path the content landed at.

    DEVELOPMENT NOTES:
    ------------------
    Every exporter and the project save shared the same four lines -
    temp file, optional .bak, os.replace, cleanup - each with its own
    copy to keep right. They call this now.

    A raise from write() propagates: callers report their own failure
    message. The temporary file is still cleaned up on the way out.
    """
    path = Path(filepath)
    temp_path = Path(f"{filepath}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write(temp_path)
        if keep_backup and path.exists():
            try:
                os.replace(path, Path(f"{filepath}.bak"))
            except OSError:
                logger.warning("Could not roll %s to the backup name; "
                               "the write continues without one", path)
        os.replace(temp_path, path)
        return path
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Could not remove the temporary file %s",
                         temp_path)


class JSONFileIO:
    """
    Handles saving and loading Project objects to/from JSON files.
    
    Includes custom JSON encoder for datetime objects.
    """
    
    @staticmethod
    def _datetime_serializer(obj: Any) -> str:
        """Custom JSON serializer for datetime objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    @staticmethod
    def _datetime_deserializer(dct: Dict[str, Any]) -> Dict[str, Any]:
        """Custom JSON deserializer for datetime strings."""
        for key, value in list(dct.items()):
            if key.endswith('_date') and value is not None and isinstance(value, str):
                try:
                    dct[key] = datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    dct[key] = None
            elif key == 'tasks' and isinstance(value, list):
                # Process each task dictionary
                processed_tasks = []
                for task in value:
                    processed_task = task.copy()
                    for task_key, task_value in task.items():
                        if task_key in ['start_date', 'end_date'] and task_value is not None and isinstance(task_value, str):
                            try:
                                processed_task[task_key] = datetime.fromisoformat(task_value)
                            except (ValueError, TypeError):
                                processed_task[task_key] = None
                    processed_tasks.append(processed_task)
                dct[key] = processed_tasks
        return dct
    
    @classmethod
    def save_project(cls, project: Project, filepath: str,
                     extra_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a Project object to a JSON file atomically.

        Args:
            project: The Project object to save
            filepath: Path to the JSON file
            extra_data: Optional dictionary of extra data to merge into the
                saved JSON (e.g. baseline slots).

        Returns:
            True if successful, False otherwise
        """
        try:
            project_dict = project.to_dict()
            if extra_data:
                project_dict.update(extra_data)

            def write(temp_path):
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(
                        project_dict,
                        f,
                        indent=2,
                        ensure_ascii=False,
                        default=cls._datetime_serializer
                    )

            atomic_write(filepath, write)
            return True
        except Exception as e:
            logger.exception(f"Error saving project: {e}")
            return False
    
    @classmethod
    def load_project(cls, filepath: str) -> Optional[Project]:
        """
        Load a Project object from a JSON file.
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            Project object if successful, None otherwise
        """
        try:
            if not os.path.exists(filepath):
                logger.warning(f"File not found: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert string dates back to datetime objects
            data = cls._datetime_deserializer(data)
            
            # Create Project from dictionary
            project = Project.from_dict(data)
            return project
            
        except json.JSONDecodeError as e:
            logger.exception(f"Error decoding JSON: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error loading project: {e}")
            return None


class ProjectFileManager:
    """
    Manages project file operations including save, load, and file dialogs.
    """
    
    def __init__(self, default_extension: str = ".json"):
        self.default_extension = default_extension
    
    def save_project_dialog(self, project: Project, initial_file: str = None) -> bool:
        """
        Save project with file dialog (to be integrated with GUI).
        
        For now, this is a placeholder that saves to a default location.
        """
        if initial_file:
            filepath = initial_file
        else:
            # Use project name as filename
            filename = f"{project.name.replace(' ', '_')}{self.default_extension}"
            filepath = filename
        
        return JSONFileIO.save_project(project, filepath)
    
    def load_project_dialog(self, filepath: str = None) -> Optional[Project]:
        """
        Load project with file dialog (to be integrated with GUI).
        
        For now, this loads from the specified filepath.
        """
        if filepath:
            return JSONFileIO.load_project(filepath)
        return None


# Convenience functions
def save_project(project: Project, filepath: str,
                 extra_data: Optional[Dict[str, Any]] = None) -> bool:
    """Save project to JSON file."""
    return JSONFileIO.save_project(project, filepath, extra_data=extra_data)


def load_project(filepath: str) -> Optional[Project]:
    """Load project from JSON file."""
    return JSONFileIO.load_project(filepath)

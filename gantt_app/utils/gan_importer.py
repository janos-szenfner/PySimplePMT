"""
GAN file importer for the Gantt Project Management Tool.

Parses GanttProject's XML-based .gan files using xml.etree.ElementTree.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from gantt_app.models import Project, Task


class GANImporter:
    """
    Imports GanttProject (.gan) files and converts them to Project objects.
    
    GanttProject files are XML-based and contain tasks, resources, and assignments.
    This importer focuses on the task structure and dependencies.
    """
    
    def __init__(self):
        # Namespace for GanttProject XML files
        self.namespaces = {
            'gn': 'http://ganttproject.sf.net/'
        }
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string from GAN file.
        
        GAN files use ISO 8601 format: yyyy-MM-dd'T'HH:mm:ss.SSSZ
        """
        if not date_str or date_str.strip() == '':
            return None
        
        try:
            # Handle different date formats
            date_str = date_str.strip()
            
            # Remove timezone indicator if present
            if date_str.endswith('Z'):
                date_str = date_str[:-1]
            
            # Try parsing with milliseconds
            if '.' in date_str:
                # Format: yyyy-MM-ddTHH:mm:ss.SSS
                return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f')
            else:
                # Format: yyyy-MM-ddTHH:mm:ss
                return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
        except (ValueError, TypeError):
            return None
    
    def parse_task(self, task_elem: ET.Element, color_map: Dict[str, str]) -> Optional[Task]:
        """
        Parse a single task element from GAN XML.
        
        Args:
            task_elem: XML element representing a task
            color_map: Dictionary mapping GanttProject colors to hex colors
            
        Returns:
            Task object or None if parsing fails
        """
        try:
            task_id = task_elem.get('id')
            name = task_elem.get('name', 'Unnamed Task')
            
            # Get start and end dates
            start_elem = task_elem.find('gn:start', self.namespaces)
            end_elem = task_elem.find('gn:end', self.namespaces)
            
            start_date = self.parse_date(start_elem.text) if start_elem is not None else None
            end_date = self.parse_date(end_elem.text) if end_elem is not None else None
            
            # Check if this is a milestone
            is_milestone = False
            duration_elem = task_elem.find('gn:duration', self.namespaces)
            if duration_elem is not None:
                duration = int(duration_elem.get('length', 0))
                if duration == 0:
                    is_milestone = True
            
            # For milestones, set end_date to None
            if is_milestone:
                end_date = None
            
            # Get progress
            completion_elem = task_elem.find('gn:completion', self.namespaces)
            progress = int(completion_elem.get('percentage', 0)) if completion_elem is not None else 0
            
            # Get color
            color_elem = task_elem.find('gn:color', self.namespaces)
            color_id = color_elem.get('id') if color_elem is not None else 'default'
            color = color_map.get(color_id, '#1f6aa5')
            
            # Get dependencies
            dependencies = []
            depends_on_elem = task_elem.find('gn:depends-on', self.namespaces)
            if depends_on_elem is not None:
                for dep_elem in depends_on_elem.findall('gn:dependency', self.namespaces):
                    dep_id = dep_elem.get('idref')
                    if dep_id:
                        dependencies.append(dep_id)
            
            # Create Task object
            task = Task(
                id=task_id,
                name=name,
                start_date=start_date or datetime.now(),
                end_date=end_date,
                progress=progress,
                dependencies=dependencies,
                color=color,
                is_milestone=is_milestone
            )
            
            return task
            
        except Exception as e:
            print(f"Error parsing task: {e}")
            return None
    
    def parse_colors(self, root: ET.Element) -> Dict[str, str]:
        """
        Parse color definitions from GAN XML.
        
        Returns:
            Dictionary mapping color IDs to hex color strings
        """
        colors = {}
        colors_elem = root.find('gn:colors', self.namespaces)
        
        if colors_elem is not None:
            for color_elem in colors_elem.findall('gn:color', self.namespaces):
                color_id = color_elem.get('id')
                r = int(color_elem.get('r', 0))
                g = int(color_elem.get('g', 0))
                b = int(color_elem.get('b', 0))
                
                # Convert RGB to hex
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                colors[color_id] = color_hex
        
        # Add default colors
        colors['default'] = '#1f6aa5'
        colors['milestone'] = '#e74c3c'
        
        return colors
    
    def parse_tasks(self, root: ET.Element) -> List[Task]:
        """
        Parse all tasks from GAN XML.
        
        Returns:
            List of Task objects
        """
        tasks = []
        color_map = self.parse_colors(root)
        
        tasks_elem = root.find('gn:tasks', self.namespaces)
        if tasks_elem is not None:
            for task_elem in tasks_elem.findall('gn:task', self.namespaces):
                task = self.parse_task(task_elem, color_map)
                if task:
                    tasks.append(task)
        
        return tasks
    
    def import_gan(self, filepath: str) -> Optional[Project]:
        """
        Import a .gan file and convert it to a Project object.
        
        Args:
            filepath: Path to the .gan file
            
        Returns:
            Project object if successful, None otherwise
        """
        try:
            if not Path(filepath).exists():
                print(f"File not found: {filepath}")
                return None
            
            # Parse XML
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Get project name
            project_name = root.get('name', 'Imported Project')
            
            # Parse tasks
            tasks = self.parse_tasks(root)
            
            # Create Project
            project = Project(name=project_name, tasks=tasks)
            
            return project
            
        except ET.ParseError as e:
            print(f"Error parsing GAN file: {e}")
            return None
        except Exception as e:
            print(f"Error importing GAN file: {e}")
            return None


class GANExporter:
    """
    Exports Project objects to GAN format (for potential future use).
    """
    
    def __init__(self):
        pass
    
    def export_gan(self, project: Project, filepath: str) -> bool:
        """
        Export a Project to GAN format.
        
        Note: This is a simplified exporter and may not include all GAN features.
        """
        try:
            # This would require implementing the full GAN XML structure
            # For now, we'll just return False as this is not a priority
            print("GAN export not yet implemented")
            return False
        except Exception as e:
            print(f"Error exporting GAN file: {e}")
            return False


# Convenience functions
def import_gan_file(filepath: str) -> Optional[Project]:
    """Import a .gan file."""
    importer = GANImporter()
    return importer.import_gan(filepath)

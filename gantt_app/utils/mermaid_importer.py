"""
Mermaid file importer and exporter for the Gantt Project Management Tool.

Handles importing and exporting Mermaid Gantt chart syntax.
Mermaid Gantt charts use a text-based format that can include project information,
tasks, milestones, and dependencies.

Example Mermaid Gantt syntax:
```mermaid
gantt
    title Project Name
    dateFormat  YYYY-MM-DD
    section Section 1
    Task 1 :a1, 2024-01-01, 7d
    Task 2 :a2, after a1, 5d
    milestone Milestone 1 :a3, after a2
    section Section 2
    Task 3 :a4, 2024-01-10, 3d
```
"""

import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from gantt_app.models import Project, Task


class MermaidImporter:
    """
    Imports Mermaid Gantt chart files and converts them to Project objects.
    
    Mermaid Gantt charts use a specific text-based syntax to define tasks,
    milestones, and their relationships.
    """
    
    def __init__(self):
        self.default_color = "#1f6aa5"
        self.milestone_color = "#e74c3c"
    
    def _parse_date(self, date_str: str, date_format: str = "%Y-%m-%d") -> Optional[datetime]:
        """Parse date string from Mermaid file."""
        if not date_str or date_str.strip() == '':
            return None
        try:
            return datetime.strptime(date_str.strip(), date_format)
        except (ValueError, TypeError):
            return None
    
    def _parse_duration(self, duration_str: str, start_date: datetime) -> Optional[datetime]:
        """Parse duration string and calculate end date."""
        if not duration_str or duration_str.strip() == '':
            return None
        
        duration_str = duration_str.strip().lower()
        match = re.match(r'^(\d+)\s*([a-z]*)$', duration_str)
        if not match:
            return None
        
        number = int(match.group(1))
        unit = match.group(2)
        
        if unit in ['d', 'day', 'days']:
            return start_date + timedelta(days=number)
        elif unit in ['w', 'week', 'weeks']:
            return start_date + timedelta(weeks=number)
        elif unit in ['m', 'month', 'months']:
            return start_date + timedelta(days=number * 30)
        else:
            return start_date + timedelta(days=number)
    
    def _strip_indentation(self, line: str) -> str:
        """Remove leading whitespace from a line."""
        return line.strip()
    
    def _extract_task_info(self, line: str) -> Optional[Dict[str, Any]]:
        """Extract task information from a Mermaid Gantt line."""
        line = self._strip_indentation(line)
        
        if not line or line.startswith('section') or line.startswith('%'):
            return None
        if line.startswith('title') or line.startswith('dateFormat'):
            return None
        
        is_milestone = False
        if line.startswith('milestone'):
            is_milestone = True
            line = line[len('milestone'):].strip()
        
        pattern = r'^(.+?)\s*:\s*([^,]+),\s*(.+)$'
        match = re.match(pattern, line)
        if not match:
            pattern = r'^([^:]+)\s*:\s*([^,]+),\s*(.+)$'
            match = re.match(pattern, line)
            if not match:
                return None
        
        name = match.group(1).strip()
        task_id = match.group(2).strip()
        rest = match.group(3).strip()
        
        task_info = {
            'name': name,
            'id': task_id,
            'is_milestone': is_milestone
        }
        
        after_match = re.match(r'after\s+([^,]+),\s*(.+)$', rest, re.IGNORECASE)
        if after_match:
            task_info['dependency'] = after_match.group(1).strip()
            task_info['duration'] = after_match.group(2).strip()
        else:
            after_simple_match = re.match(r'after\s+([^,\s].*)$', rest, re.IGNORECASE)
            if after_simple_match:
                task_info['dependency'] = after_simple_match.group(1).strip()
                if not is_milestone:
                    task_info['duration'] = '1d'
            else:
                date_part = rest.split(',')[0].strip() if ',' in rest else rest.strip()
                parsed_date = self._parse_date(date_part)
                if parsed_date:
                    task_info['start_date'] = date_part
                    if ',' in rest:
                        duration_str = rest.split(',', 1)[1].strip()
                        task_info['duration'] = duration_str
                else:
                    task_info['duration'] = rest
        
        return task_info
    
    def _extract_metadata(self, content: str) -> Dict[str, str]:
        """Extract metadata (title, dateFormat) from Mermaid content."""
        metadata = {
            'title': "Imported Mermaid Project",
            'dateFormat': "YYYY-MM-DD"
        }
        
        lines = content.split('\n')
        for line in lines:
            stripped_line = self._strip_indentation(line)
            if stripped_line.startswith('title'):
                parts = stripped_line.split(maxsplit=1)
                if len(parts) > 1:
                    metadata['title'] = stripped_line.split(' ', 1)[1].strip()
            elif stripped_line.startswith('dateFormat'):
                parts = stripped_line.split(maxsplit=1)
                if len(parts) > 1:
                    metadata['dateFormat'] = stripped_line.split(' ', 1)[1].strip()
        
        return metadata
    
    def _convert_mermaid_to_python_format(self, mermaid_format: str) -> str:
        """Convert Mermaid date format to Python datetime format."""
        format_map = {
            "YYYY-MM-DD": "%Y-%m-%d",
            "MM/DD/YYYY": "%m/%d/%Y",
            "DD/MM/YYYY": "%d/%m/%Y",
            "YYYY/MM/DD": "%Y/%m/%d",
            "DD-MM-YYYY": "%d-%m-%Y",
            "MM-DD-YYYY": "%m-%d-%Y",
        }
        return format_map.get(mermaid_format, "%Y-%m-%d")
    
    def _calculate_task_dates(self, tasks_info: List[Dict], task_map: Dict) -> None:
        """Calculate task dates based on dependencies."""
        # First pass: set explicit start dates and calculate end dates for tasks with explicit start
        for info in tasks_info:
            task_id = info['id']
            if task_id in task_map:
                task = task_map[task_id]
                if 'start_date' in info and info['start_date']:
                    start_date = self._parse_date(info['start_date'])
                    if start_date:
                        task.start_date = start_date
                
                if 'duration' in info and not info.get('is_milestone', False):
                    if task.start_date:
                        end_date = self._parse_duration(info['duration'], task.start_date)
                        if end_date:
                            task.end_date = end_date
        
        # Multiple passes to resolve dependency chains
        max_passes = len(tasks_info)
        for _ in range(max_passes):
            changed = False
            for info in tasks_info:
                task_id = info['id']
                if task_id in task_map and 'dependency' in info:
                    task = task_map[task_id]
                    dep_id = info['dependency']
                    
                    if dep_id in task_map:
                        dep_task = task_map[dep_id]
                        # For dependent tasks, set start_date to the end of the dependency
                        # For milestones, use their start_date as the point after which to continue
                        new_start_date = None
                        if dep_task.end_date:
                            new_start_date = dep_task.end_date
                        elif dep_task.is_milestone and dep_task.start_date:
                            # For milestones, dependent tasks start the same day or next day
                            new_start_date = dep_task.start_date
                        
                        if new_start_date and new_start_date != task.start_date:
                            task.start_date = new_start_date
                            
                            # Recalculate end date based on duration
                            if 'duration' in info and not info.get('is_milestone', False):
                                task.end_date = self._parse_duration(info['duration'], task.start_date)
                            elif info.get('is_milestone', False):
                                # For milestones, we might have a duration that's actually a date offset
                                # But typically milestones have explicit dates or use dependency date
                                task.end_date = None
                            changed = True
            
            if not changed:
                break
    
    def _parse_mermaid_content(self, content: str) -> Optional[Project]:
        """Parse Mermaid Gantt content and create a Project object."""
        try:
            metadata = self._extract_metadata(content)
            project_name = metadata.get('title', "Imported Mermaid Project")
            python_date_format = self._convert_mermaid_to_python_format(
                metadata.get('dateFormat', "YYYY-MM-DD")
            )
            
            lines = content.split('\n')
            tasks_info = []
            
            for line in lines:
                task_info = self._extract_task_info(line)
                if task_info:
                    tasks_info.append(task_info)
            
            tasks = []
            task_map = {}
            
            for info in tasks_info:
                task_id = info['id']
                name = info['name']
                is_milestone = info.get('is_milestone', False)
                
                start_date = datetime.now()
                
                if 'start_date' in info:
                    parsed_date = self._parse_date(info['start_date'], python_date_format)
                    if parsed_date:
                        start_date = parsed_date
                
                end_date = None
                if 'duration' in info and not is_milestone:
                    parsed_duration = self._parse_duration(info['duration'], start_date)
                    if parsed_duration:
                        end_date = parsed_duration
                
                color = self.milestone_color if is_milestone else self.default_color
                
                task = Task(
                    id=task_id,
                    name=name,
                    start_date=start_date,
                    end_date=end_date,
                    progress=0,
                    dependencies=[],
                    color=color,
                    is_milestone=is_milestone
                )
                
                tasks.append(task)
                task_map[task_id] = task
            
            for info in tasks_info:
                task_id = info['id']
                if task_id in task_map and 'dependency' in info:
                    dep_id = info['dependency']
                    task = task_map[task_id]
                    task.dependencies.append(dep_id)
            
            self._calculate_task_dates(tasks_info, task_map)
            
            project = Project(name=project_name, tasks=tasks)
            return project
            
        except Exception as e:
            print(f"Error parsing Mermaid content: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def import_mermaid(self, filepath: str) -> Optional[Project]:
        """Import a Mermaid file and convert it to a Project object."""
        try:
            if not Path(filepath).exists():
                print(f"File not found: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._parse_mermaid_content(content)
            
        except Exception as e:
            print(f"Error importing Mermaid file: {e}")
            return None


class MermaidExporter:
    """Exports Project objects to Mermaid Gantt chart format."""
    
    def __init__(self):
        pass
    
    def _generate_task_id(self, task: Task, used_ids: set) -> str:
        """Generate a unique task ID for Mermaid export."""
        if task.id and task.id not in used_ids:
            valid_id = re.sub(r'[^a-zA-Z0-9_]', '_', task.id)
            if valid_id and valid_id not in used_ids:
                used_ids.add(valid_id)
                return valid_id
        
        base_id = re.sub(r'[^a-zA-Z0-9_]', '_', task.name.lower())
        if base_id and base_id not in used_ids:
            used_ids.add(base_id)
            return base_id
        
        counter = 1
        while f"{base_id}_{counter}" in used_ids:
            counter += 1
        
        task_id = f"{base_id}_{counter}"
        used_ids.add(task_id)
        return task_id
    
    def _format_date(self, date: datetime) -> str:
        """Format datetime object as Mermaid date string."""
        return date.strftime("%Y-%m-%d")
    
    def _get_task_duration_days(self, task: Task) -> Optional[int]:
        """Get task duration in days."""
        if task.is_milestone:
            return 0
        if task.end_date is None or task.start_date is None:
            return None
        return (task.end_date - task.start_date).days + 1
    
    def export_mermaid(self, project: Project, filepath: str, 
                     include_date_format: bool = True) -> bool:
        """Export a Project to Mermaid Gantt chart format."""
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            content = self._generate_mermaid_content_with_dependencies(project, include_date_format)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error exporting Mermaid file: {e}")
            return False
    
    def _generate_mermaid_content_with_dependencies(self, project: Project, 
                                                   include_date_format: bool = True) -> str:
        """Generate Mermaid content with proper dependency handling."""
        lines = []
        used_ids = set()
        id_to_mermaid_id = {}
        
        lines.append("gantt")
        if project.name:
            lines.append(f"    title {project.name}")
        if include_date_format:
            lines.append("    dateFormat  YYYY-MM-DD")
        
        for task in project.tasks:
            mermaid_id = self._generate_task_id(task, used_ids)
            id_to_mermaid_id[task.id] = mermaid_id
        
        sorted_tasks = self._sort_tasks_for_dependencies(project)
        defined_task_ids = set()
        
        for task in sorted_tasks:
            mermaid_id = id_to_mermaid_id[task.id]
            valid_deps = [dep_id for dep_id in task.dependencies if dep_id in defined_task_ids]
            
            if task.is_milestone:
                date_str = self._format_date(task.start_date)
                if valid_deps and len(valid_deps) == 1:
                    dep_mermaid_id = id_to_mermaid_id.get(valid_deps[0], valid_deps[0])
                    lines.append(f"    milestone {task.name} :{mermaid_id}, after {dep_mermaid_id}")
                else:
                    lines.append(f"    milestone {task.name} :{mermaid_id}, {date_str}")
            else:
                date_str = self._format_date(task.start_date)
                duration_days = self._get_task_duration_days(task)
                if duration_days is None or duration_days <= 0:
                    duration_days = 1
                
                if valid_deps and len(valid_deps) == 1:
                    dep_mermaid_id = id_to_mermaid_id.get(valid_deps[0], valid_deps[0])
                    lines.append(f"    {task.name} :{mermaid_id}, after {dep_mermaid_id}, {duration_days}d")
                else:
                    lines.append(f"    {task.name} :{mermaid_id}, {date_str}, {duration_days}d")
            
            defined_task_ids.add(task.id)
        
        return "\n".join(lines)
    
    def _sort_tasks_for_dependencies(self, project: Project) -> List[Task]:
        """Sort tasks to ensure dependencies are defined before dependent tasks."""
        visited = set()
        sorted_tasks = []
        
        def visit(task: Task):
            if task.id in visited:
                return
            for dep_id in task.dependencies:
                dep_task = project.get_task_by_id(dep_id)
                if dep_task:
                    visit(dep_task)
            visited.add(task.id)
            sorted_tasks.append(task)
        
        for task in project.tasks:
            visit(task)
        
        return sorted_tasks
    
    def export_mermaid_content(self, project: Project) -> str:
        """Generate Mermaid Gantt chart content string."""
        return self._generate_mermaid_content_with_dependencies(project)


def import_mermaid_file(filepath: str) -> Optional[Project]:
    """Import a Mermaid file and return a Project object."""
    importer = MermaidImporter()
    return importer.import_mermaid(filepath)

def export_mermaid_file(project: Project, filepath: str) -> bool:
    """Export a Project to a Mermaid file."""
    exporter = MermaidExporter()
    return exporter.export_mermaid(project, filepath)
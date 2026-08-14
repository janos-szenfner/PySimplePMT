"""
Builds the Plotly figure behind every Gantt chart in the application.

WHY THIS MODULE EXISTS:
======================
The on-screen chart and the PNG, PDF and HTML exports must show the same
thing. They previously did not: the view, the PNG exporter and the PDF
exporter each carried their own copy of the drawing code - roughly 1700 lines
between them - so a fix to one silently left the others behind.

Everything now builds one figure here, and the callers differ only in what
they do with it: the view renders it to HTML for tkinterweb, the exporters
hand it to Kaleido or write it out as a standalone page.

DEVELOPMENT NOTES:
------------------
Tasks are ordered by start date and drawn at increasing y, with the y axis
reversed, so the earliest task sits at the top and the chart reads in the same
order as the task list.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go

from gantt_app.models import Project, Task
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


#: Defaults used when a caller supplies no chart settings.
DEFAULT_SETTINGS: Dict[str, Any] = {
    'font_size': 12,
    'bg_color': '#ffffff',
    'text_color': '#000000',
    'grid_color': '#ecf0f1',
    'task_color': '#1f6aa5',
    'milestone_color': '#e74c3c',
    'dependency_color': '#e74c3c',
    'critical_path_color': '#f39c12',
}

#: Vertical pixels allowed per task row before the chart starts growing.
ROW_HEIGHT = 40
MIN_HEIGHT = 600
DEFAULT_WIDTH = 1200


def _merged_settings(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine caller settings with the defaults."""
    merged = dict(DEFAULT_SETTINGS)
    if settings:
        merged.update({k: v for k, v in settings.items() if v is not None})
    return merged


def calculate_date_range(tasks: List[Task]) -> Tuple[datetime, datetime]:
    """
    Get the padded date range covering every task.

    RETURNS:
    --------
    Tuple[datetime, datetime]
        Earliest and latest dates, padded so bars do not touch the edges.
    """
    if not tasks:
        now = datetime.now()
        return now, now + timedelta(days=30)

    dates = [t.start_date for t in tasks]
    dates += [t.end_date for t in tasks if t.end_date is not None]

    min_date = min(dates)
    max_date = max(dates)

    padding = max(7, (max_date - min_date).days // 10)
    return min_date - timedelta(days=padding), max_date + timedelta(days=padding)


def _duration_days(task: Task) -> int:
    """Get a task's length in days, never less than one."""
    end = task.end_date or task.start_date
    if end < task.start_date:
        return 1
    return (end - task.start_date).days + 1


def _hover_text(task: Task, project: Project) -> str:
    """Build the tooltip shown when hovering a task bar."""
    end = task.end_date or task.start_date
    names = []
    for dep_id in task.dependency_ids:
        dep = project.get_task_by_id(dep_id)
        names.append(dep.name if dep else dep_id)

    return (
        f"<b>{task.name}</b><br>"
        f"ID: {task.id}<br>"
        f"Start: {task.start_date.strftime('%Y-%m-%d')}<br>"
        f"End: {end.strftime('%Y-%m-%d')}<br>"
        f"Duration: {_duration_days(task)} days<br>"
        f"Progress: {task.progress}%<br>"
        f"Type: {task.task_type}<br>"
        f"Dependencies: {', '.join(names) if names else 'None'}"
    )


def _add_tasks(figure: go.Figure, tasks: List[Task], project: Project,
               positions: Dict[str, int]) -> None:
    """
    Draw every non-milestone task as a horizontal bar.

    DEVELOPMENT NOTES:
    ------------------
    A task with sub-tasks brackets the work beneath it rather than being work
    of its own, so it is drawn thinner and fully opaque. The static renderer
    gives it a proper tapered bracket; Plotly has no shape for that inside a
    bar trace, so the distinction is carried by weight instead. The point is
    only that a summary row cannot be mistaken for real work.
    """
    summary_ids = project.get_summary_task_ids()

    for task in tasks:
        if task.is_milestone:
            continue

        is_summary = task.id in summary_ids

        figure.add_trace(go.Bar(
            x=[_duration_days(task) * 86400000],  # bar length in milliseconds
            y=[positions[task.id]],
            base=[task.start_date],
            orientation='h',
            name=task.name,
            width=0.35 if is_summary else 0.8,
            marker=dict(color=task.color,
                        line=dict(color='black',
                                  width=2 if is_summary else 1)),
            hovertemplate=_hover_text(task, project) + '<extra></extra>',
            showlegend=False,
            opacity=1.0 if is_summary else 0.85
        ))


def _add_milestones(figure: go.Figure, tasks: List[Task],
                    positions: Dict[str, int]) -> None:
    """Draw milestones as diamond markers with their name beside them."""
    milestones = [t for t in tasks if t.is_milestone]
    if not milestones:
        return

    figure.add_trace(go.Scatter(
        x=[m.start_date for m in milestones],
        y=[positions[m.id] for m in milestones],
        mode='markers+text',
        marker=dict(symbol='diamond', size=18,
                    color=[m.color for m in milestones],
                    line=dict(width=2, color='black')),
        text=[m.name for m in milestones],
        textposition='middle right',
        textfont=dict(size=11),
        hovertemplate='<b>%{text}</b><br>Date: %{x|%Y-%m-%d}<extra></extra>',
        showlegend=False
    ))


def _add_dependencies(figure: go.Figure, tasks: List[Task], project: Project,
                      positions: Dict[str, int], colour: str) -> None:
    """
    Draw a dotted line from each predecessor's finish to its successor's start.

    DEVELOPMENT NOTES:
    ------------------
    Every edge goes into a single trace separated by None values. One trace
    with breaks renders far faster than one trace per edge, which matters on
    a plan with a few hundred dependencies.
    """
    xs: List[Any] = []
    ys: List[Any] = []

    for task in tasks:
        if task.id not in positions:
            continue
        for dep_id in task.dependency_ids:
            dep = project.get_task_by_id(dep_id)
            if dep is None or dep.id not in positions:
                continue

            dep_x = dep.start_date if dep.is_milestone else (dep.end_date or dep.start_date)
            xs.extend([dep_x, task.start_date, None])
            ys.extend([positions[dep.id], positions[task.id], None])

    if not xs:
        return

    figure.add_trace(go.Scatter(
        x=xs, y=ys, mode='lines',
        line=dict(color=colour, width=2, dash='dot'),
        hoverinfo='skip', showlegend=False, opacity=0.7
    ))


def _add_critical_path(figure: go.Figure, project: Project,
                       positions: Dict[str, int], colour: str) -> None:
    """Overlay the critical path in its own colour."""
    critical = [t for t in project.get_critical_path() if t.id in positions]
    if not critical:
        return

    bars = [t for t in critical if not t.is_milestone]
    if bars:
        figure.add_trace(go.Bar(
            x=[_duration_days(t) * 86400000 for t in bars],
            y=[positions[t.id] for t in bars],
            base=[t.start_date for t in bars],
            orientation='h',
            marker=dict(color=colour, line=dict(width=2, color='black')),
            opacity=0.85,
            hoverinfo='skip', showlegend=False
        ))

    markers = [t for t in critical if t.is_milestone]
    if markers:
        figure.add_trace(go.Scatter(
            x=[t.start_date for t in markers],
            y=[positions[t.id] for t in markers],
            mode='markers',
            marker=dict(symbol='diamond', size=22, color=colour,
                        line=dict(width=3, color='black')),
            hoverinfo='skip', showlegend=False
        ))


def build_empty_figure(settings: Optional[Dict[str, Any]] = None,
                       width: int = DEFAULT_WIDTH) -> go.Figure:
    """Build the placeholder shown when a project has no tasks."""
    resolved = _merged_settings(settings)
    figure = go.Figure()
    figure.update_layout(
        title=dict(text="No tasks to display",
                   font=dict(size=18, color='#7f8c8d')),
        xaxis_title="Date", yaxis_title="Tasks",
        height=MIN_HEIGHT, width=width, showlegend=False,
        paper_bgcolor=resolved['bg_color'],
        plot_bgcolor=resolved['bg_color'],
        margin=dict(l=50, r=50, t=80, b=50),
        annotations=[dict(
            text="Add tasks to see the Gantt chart",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color='#7f8c8d')
        )]
    )
    return figure


def build_gantt_figure(project: Project,
                       settings: Optional[Dict[str, Any]] = None,
                       width: int = DEFAULT_WIDTH,
                       height: Optional[int] = None) -> go.Figure:
    """
    Build the Plotly figure for a project.

    PARAMETERS:
    -----------
    project : Project
        The project to draw.
    settings : Optional[Dict[str, Any]]
        Appearance overrides; see DEFAULT_SETTINGS for the accepted keys.
    width : int
        Figure width in pixels.
    height : Optional[int]
        Figure height in pixels. Derived from the task count when omitted.

    RETURNS:
    --------
    go.Figure
        A figure ready to render or export. A project with no tasks yields
        the placeholder from build_empty_figure.
    """
    resolved = _merged_settings(settings)

    if not project.tasks:
        return build_empty_figure(resolved, width=width)

    # Rows follow the task list, not the dates, so this export matches what
    # the window shows - see the same note in chart_render.layout_chart
    tasks = list(project.tasks)
    positions = {task.id: index for index, task in enumerate(tasks)}

    figure = go.Figure()
    _add_tasks(figure, tasks, project, positions)
    _add_milestones(figure, tasks, positions)
    _add_dependencies(figure, tasks, project, positions,
                      resolved['dependency_color'])
    _add_critical_path(figure, project, positions,
                       resolved['critical_path_color'])

    min_date, max_date = calculate_date_range(tasks)
    labels = [t.name[:30] + ('...' if len(t.name) > 30 else '') for t in tasks]
    font_size = resolved['font_size']
    text_color = resolved['text_color']

    figure.update_layout(
        title=dict(text=f"Gantt Chart: {project.name or 'New Project'}",
                   font=dict(size=18, color=text_color)),
        xaxis_title="Date",
        yaxis_title="Tasks",
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(len(tasks))),
            ticktext=labels,
            tickfont=dict(size=font_size, color=text_color),
            gridcolor=resolved['grid_color'],
            showgrid=True,
            # Earliest task at the top, matching the task list
            autorange='reversed'
        ),
        xaxis=dict(
            tickfont=dict(size=font_size, color=text_color),
            tickformat='%Y-%m-%d',
            gridcolor=resolved['grid_color'],
            showgrid=True,
            range=[min_date, max_date]
        ),
        height=height or max(MIN_HEIGHT, len(tasks) * ROW_HEIGHT + 100),
        width=width,
        showlegend=False,
        barmode='overlay',
        plot_bgcolor=resolved['bg_color'],
        paper_bgcolor=resolved['bg_color'],
        margin=dict(l=200, r=60, t=80, b=80),
        hovermode='closest',
        font=dict(size=font_size, color=text_color)
    )

    logger.debug("Built Gantt figure for %r with %d task(s)",
                 project.name, len(tasks))
    return figure

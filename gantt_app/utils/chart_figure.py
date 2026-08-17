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
from typing import Any, Dict, List, Optional, Set, Tuple

import plotly.graph_objects as go

from gantt_app.models import Project, Task
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


def _get_visible_tasks(project: Project) -> List[Task]:
    """
    Get tasks that should be visible in the Gantt chart.
    
    Only returns tasks where show_in_timeline is True (default).
    
    PARAMETERS:
    -----------
    project : Project
        The project containing tasks.
        
    RETURNS:
    --------
    List[Task]
        List of tasks with show_in_timeline set to True.
    """
    return [task for task in project.tasks if task.show_in_timeline]


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


def _elapsed_days(task: Task) -> int:
    """
    How many calendar days a task spans, never less than one.

    DEVELOPMENT NOTES:
    ------------------
    This is what a bar is drawn across, so it has to be elapsed time: a bar is
    placed on a date axis and a weekend inside a task is calendar the bar has
    to cover. Task.duration_days is the working effort inside it, which is a
    smaller number for anything crossing a weekend - see
    gantt_app.workdaycalendar - and using it here drew every such bar short.
    """
    end = task.end_date or task.start_date
    if end < task.start_date:
        return 1
    return (end - task.start_date).days + 1


def _hover_text(task: Task, project: Project) -> str:
    """
    Build the tooltip shown when hovering a task bar.

    Both measures are given: the working days the task holds, and the calendar
    days it is spread over. A reader looking at a bar that runs over a weekend
    is owed the explanation of why it is longer than its duration.
    """
    end = task.end_date or task.start_date
    names = []
    for dep_id in task.dependency_ids:
        dep = project.get_task_by_id(dep_id)
        names.append(dep.name if dep else dep_id)

    duration = task.duration_days
    duration_text = "-" if duration is None else f"{duration} working day(s)"
    elapsed = _elapsed_days(task)

    return (
        f"<b>{task.name}</b><br>"
        f"ID: {task.id}<br>"
        f"Start: {task.start_date.strftime('%Y-%m-%d')}<br>"
        f"End: {end.strftime('%Y-%m-%d')}<br>"
        f"Duration: {duration_text}<br>"
        f"Elapsed: {elapsed} calendar day(s)<br>"
        f"Progress: {task.progress}%<br>"
        f"Type: {task.task_type}<br>"
        f"Dependencies: {', '.join(names) if names else 'None'}"
    )


#: Half-height of a task bar, in row units, and how much of a Phase's length
#: its arrow head takes up.
BAR_HALF_HEIGHT = 0.4
PHASE_HEAD_FRACTION = 0.12
PHASE_HEAD_MAX_DAYS = 4


def _phase_outline(task: Task) -> Tuple[List[Any], List[float]]:
    """
    The pointed shape a Phase row is drawn in, as x and y coordinates.

    RETURNS:
    --------
    Tuple[List[Any], List[float]]
        Dates and row offsets tracing a full-height bar whose right-hand end
        is drawn to a point, closed back to where it started.

    DEVELOPMENT NOTES:
    ------------------
    The head is a fraction of the phase's own length rather than a fixed number
    of pixels, because a Plotly trace is placed in dates and rows and knows
    nothing about how wide it will be drawn. It is capped so a year-long phase
    does not get a head a month and a half deep, and it can never eat the whole
    span, which would fold the shape through itself.
    """
    start = task.start_date
    # A task is inclusive of its end date, so the shape covers that whole day
    end = (task.end_date or task.start_date) + timedelta(days=1)

    span_days = max((end - start).days, 1)
    head_days = min(max(span_days * PHASE_HEAD_FRACTION, 0.5),
                    PHASE_HEAD_MAX_DAYS, span_days)
    shoulder = end - timedelta(days=head_days)

    row = 0.0
    top, bottom = row - BAR_HALF_HEIGHT, row + BAR_HALF_HEIGHT

    return ([start, shoulder, end, shoulder, start, start],
            [top, top, row, bottom, bottom, top])


def _add_tasks(figure: go.Figure, tasks: List[Task], project: Project,
               positions: Dict[str, int],
               critical_colour: str, critical_ids: Set[str]) -> None:
    """
    Draw every non-milestone task as a horizontal bar.

    DEVELOPMENT NOTES:
    ------------------
    Three shapes, matching chart_render so the window, the static exports and
    this HTML one show the same plan:

      * A Phase is a full-height bar drawn to a point at its finish. Plotly has
        no arrow-ended bar, so it is a filled scatter trace instead - which
        still carries the same hover text, so nothing is lost by it.
      * Any other task with sub-tasks brackets the work beneath it rather than
        being work of its own, so it is drawn thinner and fully opaque. There is
        no tapered bracket to be had inside a bar trace, so that distinction is
        carried by weight; the point is only that a summary row cannot be
        mistaken for real work.
      * Everything else is an ordinary bar.

    A Phase on the critical path is painted in the critical colour here rather
    than having a bar overlaid on it by _add_critical_path, which would cover
    the point with a rectangle and lose the shape. Only a Phase with nothing
    inside it can be on the path at all - get_critical_path looks through
    anything with children - but that is exactly the Phase somebody has just
    created and is looking at.
    """
    summary_ids = project.get_summary_task_ids()

    for task in tasks:
        if task.effective_milestone:
            continue

        hover = _hover_text(task, project) + '<extra></extra>'

        # A Phase keeps its shape whether or not anything hangs off it yet
        if task.task_type == 'Phase':
            xs, offsets = _phase_outline(task)
            row = positions[task.id]
            figure.add_trace(go.Scatter(
                x=xs,
                y=[row + offset for offset in offsets],
                mode='lines',
                fill='toself',
                fillcolor=(critical_colour if task.id in critical_ids
                           else task.color),
                line=dict(color='black', width=1),
                name=task.name,
                hoveron='fills',
                hovertemplate=hover,
                showlegend=False,
            ))
            continue

        is_summary = task.id in summary_ids

        figure.add_trace(go.Bar(
            x=[_elapsed_days(task) * 86400000],  # bar length in milliseconds
            y=[positions[task.id]],
            base=[task.start_date],
            orientation='h',
            name=task.name,
            width=0.35 if is_summary else 0.8,
            marker=dict(color=task.color,
                        line=dict(color='black',
                                  width=2 if is_summary else 1)),
            hovertemplate=hover,
            showlegend=False,
            opacity=1.0 if is_summary else 0.85
        ))


def _add_milestones(figure: go.Figure, tasks: List[Task],
                    positions: Dict[str, int]) -> None:
    """Draw milestones as diamond markers with their name beside them."""
    milestones = [t for t in tasks if t.effective_milestone]
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
    """
    Overlay the critical path in its own colour.

    Phases are left out: an overlaid bar is a rectangle, which would cover the
    point a Phase is drawn with. _add_tasks paints those in the critical colour
    directly instead.
    """
    critical = [t for t in project.get_critical_path() if t.id in positions]
    if not critical:
        return

    bars = [t for t in critical
            if not t.is_milestone and t.task_type != 'Phase']
    if bars:
        figure.add_trace(go.Bar(
            x=[_elapsed_days(t) * 86400000 for t in bars],
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

    # Get only tasks that should be visible in the timeline
    visible_tasks = _get_visible_tasks(project)
    if not visible_tasks:
        return build_empty_figure(resolved, width=width)

    # Rows follow the task list, not the dates, so this export matches what
    # the window shows - see the same note in chart_render.layout_chart
    tasks = visible_tasks
    positions = {task.id: index for index, task in enumerate(tasks)}

    critical_ids = {t.id for t in project.get_critical_path()}

    figure = go.Figure()
    _add_tasks(figure, tasks, project, positions,
               resolved['critical_path_color'], critical_ids)
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

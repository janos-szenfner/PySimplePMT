"""
The pages of the PDF: the work item list, the chart, and the two together.

WHY THIS MODULE EXISTS:
======================
A PDF of the chart alone is half a plan. The bars say when work happens and
nothing else - not what a row is called past the few characters that fit
beside it, not how long it is, not what it waits for. Printed and handed
round, that is a picture rather than a document.

So the export is three pages, and each answers a different question:

  1. **The list beside the chart** - the plan as the application shows it, and
     the page somebody reads first.
  2. **The chart alone** - the same bars across the full width of the page,
     for the wall or the projector, where the dates matter and the detail is
     in the way.
  3. **The list as a table** - every column of it, the way a spreadsheet would
     lay it out, for the reader who wants the numbers rather than the shape.

DEVELOPMENT NOTES:
------------------
Pages are a fixed physical size - A4 landscape by default - rather than
whatever size the content came out. A PDF page is pixels plus a resolution,
and getting that wrong is what made the old single-page export print badly: it
saved a 2800 pixel image at 150 dpi, which is a page eighteen inches wide that
every printer then shrank by an arbitrary amount.

The chart is drawn by chart_render, at the row height this module hands it, so
the rows on page one line up with the list beside them - the same RowPlan the
on-screen view uses to keep its two panes in step.

Nothing here needs a display, and Pillow is the only dependency.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from gantt_app.models import Project, Task
from gantt_app.utils.chart_render import RowPlan, _font, render_image
from gantt_app.utils.log import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

#: Page size in inches. A4 landscape: the chart is wider than it is tall, and
#: a portrait page wastes half of itself on a plan of any length.
PAGE_INCHES = (11.69, 8.27)

#: Pixels per inch the pages are rendered at.
#:
#: 200 rather than 150: at 150 the text in the table is legible on screen and
#: ragged on paper, which is where a plan of this kind usually ends up. Higher
#: than 200 doubles the file for a difference nobody sees.
PAGE_DPI = 200

#: Margin around the content, in inches.
PAGE_MARGIN_INCHES = 0.4

#: Colours. Deliberately the task list's own, so the page and the window
#: read as the same table.
PAGE_BG = '#ffffff'
GRID_LINE = '#d0d0d0'
HEADING_BG = '#e4e4e4'
ROW_BG = '#ffffff'
ROW_ALT = '#f4f4f4'
TEXT = '#1a1a1a'
TITLE_TEXT = '#1f4e79'
FOOTER_TEXT = '#7f8c8d'

#: The columns of the work item table, as (key, heading, width in parts).
#:
#: The key is what picks the value out of a row, so a page asking for fewer
#: columns gets the right values in them. Paired by position instead, a page
#: showing five of the eight put Type under Start and Duration under End -
#: every cell filled, every one of them wrong.
#:
#: Widths are proportions of whatever the table is given, so the same
#: definition lays out beside a chart and across a whole page.
TABLE_COLUMNS = (
    ('id', 'ID', 0.6),
    ('name', 'Name', 3.6),
    ('type', 'Type', 1.0),
    ('duration', 'Duration', 0.9),
    ('start', 'Start', 1.2),
    ('end', 'End', 1.2),
    ('progress', 'Progress', 0.9),
    ('dependencies', 'Dependencies', 2.2),
)

#: The columns page one has room for beside a chart: the ones that identify
#: a row rather than describe it. The rest is what page three is for.
SUMMARY_COLUMNS = (
    ('id', 'ID', 0.7),
    ('name', 'Name', 4.0),
    ('start', 'Start', 1.6),
    ('end', 'End', 1.6),
    ('duration', 'Duration', 1.1),
)

#: How deep one level of the hierarchy is indented, in characters.
INDENT_CHARS = 2


def page_size() -> Tuple[int, int]:
    """The page in pixels, at PAGE_DPI."""
    return (int(PAGE_INCHES[0] * PAGE_DPI), int(PAGE_INCHES[1] * PAGE_DPI))


def _margin() -> int:
    """The margin in pixels."""
    return int(PAGE_MARGIN_INCHES * PAGE_DPI)


def _visible_tasks(project: Project) -> List[Task]:
    """The rows to print: whatever the timeline is showing."""
    return [task for task in project.tasks if task.show_in_timeline]


def _depth_of(project: Project, task: Task) -> int:
    """How far below the top of the plan a task sits."""
    depth = 0
    seen = {task.id}
    current = task
    while current.parent_task_id and current.parent_task_id not in seen:
        parent = project.get_task_by_id(current.parent_task_id)
        if parent is None:
            break
        seen.add(parent.id)
        current = parent
        depth += 1
    return depth


def _cells(project: Project, task: Task) -> Dict[str, str]:
    """One row of the table, as text, keyed by column."""
    depth = _depth_of(project, task)
    dependencies = []
    for dep_id in task.dependency_ids:
        found = project.get_task_by_id(dep_id)
        dependencies.append(found.name if found else dep_id)

    if task.is_container:
        duration = project.working_duration(task)
    else:
        duration = task.duration_days

    return {
        'id': str(task.id),
        'name': ' ' * (depth * INDENT_CHARS) + task.name,
        'type': task.task_type,
        'duration': '' if duration is None else str(duration),
        'start': task.start_date.strftime('%Y-%m-%d'),
        'end': task.end_date.strftime('%Y-%m-%d') if task.end_date else '—',
        'progress': f"{task.progress}%",
        'dependencies': ', '.join(dependencies),
    }


# ---------------------------------------------------------------------------
# The work item table
# ---------------------------------------------------------------------------

def _column_widths(total: int, columns=TABLE_COLUMNS) -> List[int]:
    """Share the available width out between the columns, by their parts."""
    parts = sum(part for _key, _heading, part in columns)
    return [max(int(total * part / parts), 1)
            for _key, _heading, part in columns]


def _fit(draw, text: str, font, width: int) -> str:
    """
    Trim text to the width of its cell, ending in an ellipsis.

    Measured rather than counted in characters: a name of twenty narrow
    letters fits where twenty wide ones do not, and cutting by count either
    wastes half the column or overruns it.
    """
    if not text:
        return ''
    if draw.textlength(text, font=font) <= width:
        return text

    ellipsis = '…'
    trimmed = text
    while trimmed and draw.textlength(trimmed + ellipsis, font=font) > width:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ''


def render_task_table(project: Project, width: int, row_height: int,
                      font_size: int, columns=TABLE_COLUMNS,
                      heading_height: Optional[int] = None,
                      critical: Optional[set] = None) -> Image.Image:
    """
    Draw the work item list as a table.

    PARAMETERS:
    -----------
    project : Project
        The plan to list.
    width : int
        How wide to draw it, in pixels.
    row_height : int
        Pixels per row. Beside a chart this is the chart's own row height, so
        the two line up.
    font_size : int
        Text size in pixels.
    columns : Sequence[Tuple[str, str, float]]
        Which columns to draw, as (key, heading, share of the width).
    heading_height : Optional[int]
        Height of the heading band. Defaults to one row.
    critical : Optional[set]
        Task IDs on the critical path, marked in the table so the page says
        what the chart's colouring says.

    RETURNS:
    --------
    Image.Image
        The table, exactly as tall as its heading and rows need.
    """
    tasks = _visible_tasks(project)
    heading_height = heading_height or row_height
    height = heading_height + len(tasks) * row_height

    image = Image.new('RGB', (width, max(height, heading_height)), ROW_BG)
    draw = ImageDraw.Draw(image)

    heading_font = _font(int(font_size * 1.0))
    body_font = _font(font_size)
    widths = _column_widths(width, columns)
    padding = max(3, font_size // 3)

    # The heading band
    draw.rectangle([(0, 0), (width, heading_height)], fill=HEADING_BG)
    x = 0
    for (_key, heading, _part), column_width in zip(columns, widths):
        draw.text((x + padding, heading_height / 2),
                  _fit(draw, heading, heading_font, column_width - padding * 2),
                  font=heading_font, fill=TEXT, anchor='lm')
        x += column_width
        draw.line([(x, 0), (x, height)], fill=GRID_LINE, width=1)

    # The rows
    for index, task in enumerate(tasks):
        top = heading_height + index * row_height
        if index % 2:
            draw.rectangle([(0, top), (width, top + row_height)], fill=ROW_ALT)

        cells = _cells(project, task)
        x = 0
        for (key, _heading, _part), column_width in zip(columns, widths):
            draw.text((x + padding, top + row_height / 2),
                      _fit(draw, cells.get(key, ''), body_font,
                           column_width - padding * 2),
                      font=body_font, fill=TEXT, anchor='lm')
            x += column_width

        draw.line([(0, top), (width, top)], fill=GRID_LINE, width=1)

    draw.rectangle([(0, 0), (width - 1, max(height, heading_height) - 1)],
                   outline=GRID_LINE, width=1)
    return image


# ---------------------------------------------------------------------------
# The pages
# ---------------------------------------------------------------------------

def _blank_page() -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    """A page of the right size, in the right colour."""
    image = Image.new('RGB', page_size(), PAGE_BG)
    return image, ImageDraw.Draw(image)


def _write_furniture(draw, project: Project, subtitle: str,
                     page_number: int, pages: int) -> int:
    """
    Put the title on a page and the footer under it.

    RETURNS:
    --------
    int
        The y the page's content may start at, below the title.
    """
    width, height = page_size()
    margin = _margin()

    title_font = _font(int(PAGE_DPI * 0.13))
    subtitle_font = _font(int(PAGE_DPI * 0.075))
    footer_font = _font(int(PAGE_DPI * 0.055))

    draw.text((margin, margin), project.name or 'Project',
              font=title_font, fill=TITLE_TEXT, anchor='la')
    draw.text((margin, margin + int(PAGE_DPI * 0.16)), subtitle,
              font=subtitle_font, fill=TEXT, anchor='la')

    stamp = datetime.now().strftime('%Y-%m-%d')
    draw.text((margin, height - margin), stamp,
              font=footer_font, fill=FOOTER_TEXT, anchor='ls')
    draw.text((width - margin, height - margin),
              f"Page {page_number} of {pages}",
              font=footer_font, fill=FOOTER_TEXT, anchor='rs')

    return margin + int(PAGE_DPI * 0.30)


def _fit_into(image: Image.Image, box: Tuple[int, int]) -> Image.Image:
    """
    Shrink an image to fit a box, keeping its shape.

    Only ever smaller: a chart of four rows blown up to fill a page is a
    handful of enormous bars, which says less than the same chart at its own
    size does.
    """
    width, height = box
    if image.width <= width and image.height <= height:
        return image

    scale = min(width / image.width, height / image.height)
    return image.resize(
        (max(int(image.width * scale), 1), max(int(image.height * scale), 1)),
        Image.LANCZOS,
    )


def _chart_for(project: Project, settings, width: int,
               rows: Optional[RowPlan] = None) -> Image.Image:
    """The chart at a given width, drawn for print rather than for a screen."""
    return render_image(project, settings=settings, width=width,
                        scale=2.0, min_width=width, rows=rows)


def _page_list_and_chart(project: Project, settings, number: int,
                         pages: int) -> Image.Image:
    """
    Page one: the plan as the application shows it.

    DEVELOPMENT NOTES:
    ------------------
    The chart is given the table's row height and the height of its heading
    as a top margin, so row one of the list sits level with bar one - the
    same RowPlan the on-screen view uses to keep its two panes in step.

    The list takes the narrower share of the width. Its columns are the ones
    that identify a row rather than describe it; the rest of them are what
    page three is for.
    """
    image, draw = _blank_page()
    width, height = page_size()
    margin = _margin()
    top = _write_furniture(draw, project, "Work items and schedule",
                           number, pages)

    tasks = _visible_tasks(project)
    if not tasks:
        draw.text((width / 2, height / 2), "This plan has no work items yet.",
                  font=_font(int(PAGE_DPI * 0.09)), fill=FOOTER_TEXT,
                  anchor='mm')
        return image

    available_width = width - margin * 2
    available_height = height - top - margin - int(PAGE_DPI * 0.25)

    table_width = int(available_width * 0.42)
    gap = int(PAGE_DPI * 0.08)
    chart_width = available_width - table_width - gap

    # A row height that fits the plan on one page, within reason
    row_height = max(
        int(PAGE_DPI * 0.10),
        min(int(PAGE_DPI * 0.18),
            available_height // max(len(tasks) + 3, 1))
    )
    heading_height = int(row_height * 2.4)
    font_size = max(8, int(row_height * 0.42))

    table = render_task_table(project, table_width, row_height, font_size,
                              columns=SUMMARY_COLUMNS,
                              heading_height=heading_height)
    chart = _chart_for(project, settings, chart_width,
                       rows=RowPlan(tasks=tasks, row_height=row_height,
                                    top_margin=heading_height, label_width=0))

    # Both are pasted at the same top edge, which is what lines the rows up.
    # Whichever is taller decides how much has to be given back.
    tallest = max(table.height, chart.height)
    if tallest > available_height:
        shrink = available_height / tallest
        table = table.resize((max(int(table.width * shrink), 1),
                              max(int(table.height * shrink), 1)),
                             Image.LANCZOS)
        chart = chart.resize((max(int(chart.width * shrink), 1),
                              max(int(chart.height * shrink), 1)),
                             Image.LANCZOS)

    image.paste(table, (margin, top))
    image.paste(chart, (margin + table.width + gap, top))
    return image


def _page_chart_only(project: Project, settings, number: int,
                     pages: int) -> Image.Image:
    """Page two: the bars across the width of the page."""
    image, draw = _blank_page()
    width, height = page_size()
    margin = _margin()
    top = _write_furniture(draw, project, "Schedule", number, pages)

    if not _visible_tasks(project):
        draw.text((width / 2, height / 2), "This plan has no work items yet.",
                  font=_font(int(PAGE_DPI * 0.09)), fill=FOOTER_TEXT,
                  anchor='mm')
        return image

    available_width = width - margin * 2
    available_height = height - top - margin - int(PAGE_DPI * 0.25)

    chart = _fit_into(_chart_for(project, settings, available_width),
                      (available_width, available_height))
    image.paste(chart, (margin + (available_width - chart.width) // 2, top))
    return image


def _page_table(project: Project, settings, number: int,
                pages: int) -> Image.Image:
    """Page three: every column, the way a spreadsheet would lay it out."""
    image, draw = _blank_page()
    width, height = page_size()
    margin = _margin()
    top = _write_furniture(draw, project, "Work item list", number, pages)

    tasks = _visible_tasks(project)
    if not tasks:
        draw.text((width / 2, height / 2), "This plan has no work items yet.",
                  font=_font(int(PAGE_DPI * 0.09)), fill=FOOTER_TEXT,
                  anchor='mm')
        return image

    available_width = width - margin * 2
    available_height = height - top - margin - int(PAGE_DPI * 0.25)

    row_height = max(
        int(PAGE_DPI * 0.10),
        min(int(PAGE_DPI * 0.16),
            available_height // max(len(tasks) + 2, 1))
    )
    font_size = max(8, int(row_height * 0.42))

    table = _fit_into(
        render_task_table(project, available_width, row_height, font_size,
                          heading_height=int(row_height * 1.3)),
        (available_width, available_height),
    )
    image.paste(table, (margin, top))
    return image


def render_pages(project: Project,
                 settings: Optional[Dict[str, Any]] = None
                 ) -> List[Image.Image]:
    """
    Draw the pages of the exported document.

    RETURNS:
    --------
    List[Image.Image]
        Three pages: the list beside the chart, the chart alone, and the
        list as a full table. Each is the same physical size, so the PDF
        prints as one document rather than three shapes.
    """
    builders = (_page_list_and_chart, _page_chart_only, _page_table)
    total = len(builders)
    return [build(project, settings, number, total)
            for number, build in enumerate(builders, start=1)]

"""
The dashboard's panel machinery and the timeline, tested without a screen.

WHY THIS FILE:
==============
The boards' drawing lives in utils.boardrender and draws through a pen,
so everything about them except the widgets can be checked headlessly:
the panel registry and its four-panel cap, the grid layout, the
timeline's flagged-rows rule and its five styles, and the PNG/PDF
exports - ImagePen and Pillow need no display, which is the whole
reason the drawing was written against a pen (issues #66, #83).
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

from gantt_app.core.models import Project, Task
from gantt_app.utils import boardrender
from gantt_app.core.deliverable import Deliverable
from gantt_app.utils.boardrender import (
    DASHBOARD_PANELS, MAX_PANELS, TIMELINE_STYLES,
    dashboard_layout, dashboard_rows, deliverable_rows,
    render_dashboard, render_timeline,
    sanitize_panel_ids, timeline_items, timeline_span, axis_columns,
)
from gantt_app.utils.drawpen import ImagePen

BASE = datetime(2026, 1, 5)

#: A palette that stands in for the theme - the drawing reads keys, not
#: appearances, so a fixed light set is enough to test against.
PALETTE = {
    'bg': '#f5f6f8', 'panel_bg': '#ffffff', 'title': '#1f2328',
    'tick': '#4a5568', 'axis': '#8a9199', 'grid': '#e2e5e9',
    'progress_bar': '#3b82f6', 'progress_under': '#1c2b3a',
    'duration_bar': '#10b981',
    'series': ['#4f46e5', '#059669', '#d97706', '#dc2626'],
    'kpi_bg': '#eef1f5', 'kpi_border': '#c8cdd2',
    'header_bg': '#eef1f5', 'header_text': '#4a5568',
    'band_bg': '#3f4753', 'band_text': '#ffffff',
    'lane_bg': '#f4f5f7', 'lane_text': '#1f2328',
    'spine': '#2f3552', 'today': '#2e7d32',
    'health': {
        'done': '#15803d', 'on_track': '#1565c0',
        'not_started': '#6b7280', 'at_risk': '#b45309',
        'overdue': '#b91c1c',
    },
}


def a_project(**flags) -> Project:
    """
    A two-phase plan with flagged and unflagged rows.

    **flags marks tasks that go on the timeline by id - a_project(
    flag={'t1', 't2'}) puts those two on it.
    """
    flag = flags.get('flag', set())
    project = Project(name="Boards")
    rows = [
        ('t1', 'Phase One', 'Phase', 20, 40, None, False),
        ('t2', 'Build it', 'Task', 10, 50, 't1', False),
        ('t3', 'First stone', 'Task', 0, 0, 't1', True),
        ('t4', 'Phase Two', 'Phase', 15, 0, None, False),
        ('t5', 'Ship it', 'Task', 15, 10, 't4', False),
        ('t6', 'Loose row', 'Task', 5, 0, None, False),
    ]
    for task_id, name, kind, days, pct, parent, milestone in rows:
        project.add_task(Task(
            id=task_id, name=name, task_type=kind,
            start_date=BASE, end_date=BASE + timedelta(days=days or 1),
            duration=days, progress=pct, parent_task_id=parent,
            is_milestone=milestone,
            show_in_timeline=task_id in flag))
    return project


def an_image_pen(width=800, height=600):
    """A pen that draws into memory, and the drawing calls it recorded."""
    from PIL import Image
    image = Image.new('RGB', (width, height), 'white')
    return ImagePen(image, 1.0), image


class TestThePanelRegistry(unittest.TestCase):
    """What the dashboard can show, and the rules around it (issue #66)."""

    def test_the_panels_are_the_registry(self):
        """The built-ins, in the order the checklist lists them."""
        self.assertEqual([pid for pid, _t, _d in DASHBOARD_PANELS],
                         ['progress', 'donut', 'workload', 'summary',
                          'deliverables'])
        self.assertEqual(MAX_PANELS, 6)

    def test_sanitize_drops_names_the_registry_does_not_know(self):
        """A settings file that names a gone panel does not draw a gap."""
        self.assertEqual(
            sanitize_panel_ids(['progress', 'nonsense', 'summary']),
            ['progress', 'summary'])

    def test_sanitize_stops_at_the_cap(self):
        """A file holding more panels than fit keeps the first of them."""
        saved = (boardrender.all_panel_ids()
                 + ['progress', 'donut', 'workload', 'summary'])
        self.assertEqual(len(sanitize_panel_ids(saved)), MAX_PANELS)

    def test_sanitize_empty_is_empty(self):
        """And None comes back as an empty list the caller fills."""
        self.assertEqual(sanitize_panel_ids(None), [])
        self.assertEqual(sanitize_panel_ids([]), [])


class TestTheGridLayout(unittest.TestCase):
    """One to four panels, two to a row (issue #66)."""

    def test_one_panel_gets_the_whole_board(self):
        self.assertEqual(dashboard_layout(1, 800, 600),
                         [(0, 0, 800, 600)])

    def test_two_panels_share_a_row(self):
        self.assertEqual(dashboard_layout(2, 800, 600),
                         [(0, 0, 400, 600), (400, 0, 400, 600)])

    def test_three_panels_are_two_and_one(self):
        cells = dashboard_layout(3, 800, 600)
        self.assertEqual(len(cells), 3)
        self.assertEqual(cells[0], (0, 0, 400, 300))
        self.assertEqual(cells[1], (400, 0, 400, 300))
        self.assertEqual(cells[2], (0, 300, 400, 300))

    def test_four_panels_make_the_two_by_two(self):
        cells = dashboard_layout(4, 800, 600)
        self.assertEqual(len(cells), 4)
        self.assertEqual(cells[3], (400, 300, 400, 300))

    def test_nothing_lays_out_nothing(self):
        self.assertEqual(dashboard_layout(0, 800, 600), [])


class TestRenderingTheDashboard(unittest.TestCase):
    """The enabled panels drawn through an ImagePen."""

    def setUp(self):
        self.project = a_project()
        self.rows = dashboard_rows(self.project)

    def render(self, enabled, maximized=None):
        pen, image = an_image_pen()
        landed = render_dashboard(pen, self.rows, PALETTE, enabled,
                                  maximized, width=800, height=600)
        return landed, image

    def test_each_enabled_panel_reports_where_it_landed(self):
        landed, _image = self.render(['progress', 'summary'])
        self.assertEqual([p['id'] for p in landed],
                         ['progress', 'summary'])
        self.assertEqual(len(landed), 2)

    def test_a_maximized_panel_is_the_only_one_drawn(self):
        landed, _image = self.render(
            ['progress', 'donut', 'summary'], maximized='donut')
        self.assertEqual([p['id'] for p in landed], ['donut'])
        # The whole board is its cell - the render used the full width.
        x0, _y0, x1, _y1 = landed[0]['rect']
        self.assertGreater(x1 - x0, 700)

    def test_a_maximized_id_that_is_off_is_ignored(self):
        """Off + maximized is a contradiction; the grid wins."""
        landed, _image = self.render(['progress'], maximized='summary')
        self.assertEqual([p['id'] for p in landed], ['progress'])

    def test_an_empty_plan_says_so_instead_of_drawing(self):
        pen, _image = an_image_pen()
        landed = render_dashboard(pen, [], PALETTE,
                                  boardrender.all_panel_ids(),
                                  None, width=800, height=600)
        self.assertEqual(landed, [])


class _RecordingPen:
    """
    A pen that only remembers - for what the drawing asked to be painted.

    ImagePen proves the calls can run; this one answers what the calls
    were, which is what the health-colour tests are about.
    """

    def __init__(self):
        self.rects = []      # (x0, y0, x1, y1, fill, outline)
        self.texts = []

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        self.rects.append((x0, y0, x1, y1, fill, outline))

    def line(self, *args, **kwargs):
        pass

    def text(self, *args, **kwargs):
        self.texts.append((args, kwargs))

    def arc(self, *args, **kwargs):
        pass

    def text_width(self, text, size, bold=False):
        return len(str(text)) * size


class TestTheDeliverablesPanel(unittest.TestCase):
    """The dashboard's fifth panel: the top-level deliverables (#120)."""

    def _project_with_deliverables(self):
        project = a_project()
        parent = Deliverable(id='d1', name='The product',
                             progress=50, status='In Progress')
        child = Deliverable(id='d2', name='The installer',
                            parent_id='d1', progress=25)
        overdue = Deliverable(id='d3', name='The manual',
                              due_date=datetime(2020, 1, 1))
        project.deliverables.extend([parent, child, overdue])
        return project

    def test_only_the_top_level_is_listed(self):
        """Main deliverables, not every sub-deliverable beneath them."""
        rows = deliverable_rows(self._project_with_deliverables())

        self.assertEqual([row['Name'] for row in rows],
                         ['The product', 'The manual'])

    def test_each_row_carries_its_progress_and_health(self):
        rows = deliverable_rows(self._project_with_deliverables())

        self.assertEqual(rows[0]['Progress'], 50)
        self.assertEqual(rows[0]['Health'], 'on_track')
        # Owed in 2020 and not finished: red.
        self.assertEqual(rows[1]['Health'], 'overdue')

    def test_a_project_with_none_lists_none(self):
        self.assertEqual(deliverable_rows(a_project()), [])
        self.assertEqual(deliverable_rows(None), [])

    def test_the_panel_draws_in_its_health_colours(self):
        """A bar's fill is the colour its state wears on the board."""
        pen = _RecordingPen()
        deliverables = deliverable_rows(
            self._project_with_deliverables())

        boardrender.draw_deliverables(pen, deliverables, PALETTE,
                                      0, 0, 800, 600)

        fills = [fill for _x0, _y0, _x1, _y1, fill, _o in pen.rects
                 if fill]
        self.assertIn(PALETTE['health']['on_track'], fills)
        # The overdue row holds no progress to fill - the colour lives in
        # its percentage instead.
        text_fills = [kw.get('fill') for _a, kw in pen.texts]
        self.assertIn(PALETTE['health']['overdue'], text_fills)

    def test_the_panel_says_so_when_there_are_none(self):
        pen = _RecordingPen()

        boardrender.draw_deliverables(pen, [], PALETTE, 0, 0, 800, 600)

        self.assertTrue(any('No deliverables' in str(args)
                            for args, _kw in pen.texts))

    def test_it_lands_on_the_board_like_every_panel(self):
        pen, _image = an_image_pen()
        landed = render_dashboard(
            pen, dashboard_rows(a_project()), PALETTE,
            ['deliverables'], None, width=800, height=600,
            deliverables=deliverable_rows(
                self._project_with_deliverables()))

        self.assertEqual([p['id'] for p in landed], ['deliverables'])

    def test_deliverables_alone_are_not_an_empty_plan(self):
        """A plan with deliverables and no tasks still has a board."""
        project = Project(name="Deliverables only")
        project.deliverables.append(Deliverable(id='d1', name='One'))
        pen, _image = an_image_pen()

        landed = render_dashboard(
            pen, [], PALETTE, ['deliverables'], None,
            width=800, height=600,
            deliverables=deliverable_rows(project))

        self.assertEqual([p['id'] for p in landed], ['deliverables'])


class TestTheTimelineRows(unittest.TestCase):
    """Which rows the timeline draws (issue #83)."""

    def test_only_flagged_rows_are_items(self):
        items = timeline_items(a_project(flag={'t2', 't5'}))
        self.assertEqual([item['name'] for item in items],
                         ['Build it', 'Ship it'])

    def test_items_know_their_lane(self):
        """A flagged row lanes under its top-level ancestor."""
        items = timeline_items(a_project(flag={'t2', 't6'}))
        lanes = {item['name']: item['lane'] for item in items}
        self.assertEqual(lanes['Build it'], 'Phase One')
        # A top-level row has no ancestor to lane under - it is its own.
        self.assertIsNone(lanes['Loose row'])

    def test_items_come_in_plan_order(self):
        items = timeline_items(a_project(flag={'t5', 't2'}))
        self.assertEqual([item['name'] for item in items],
                         ['Build it', 'Ship it'])

    def test_a_row_with_no_start_is_left_off(self):
        project = a_project(flag={'t1'})
        project.get_task_by_id('t1').start_date = None
        self.assertEqual(timeline_items(project), [])

    def test_no_flags_is_no_items(self):
        self.assertEqual(timeline_items(a_project()), [])
        self.assertEqual(timeline_items(None), [])


class TestTheTimelineStyles(unittest.TestCase):
    """Every style draws; none raises; the empty plan gets its hint."""

    def setUp(self):
        self.project = a_project(flag={'t1', 't2', 't3', 't5'})
        self.items = timeline_items(self.project)
        self.assertTrue(self.items)

    def test_five_styles_are_registered(self):
        """The five looks from the issue's examples - not MS Project's."""
        self.assertEqual(
            [sid for sid, _l, _d in TIMELINE_STYLES],
            ['lanes', 'roadmap', 'callouts', 'chevrons', 'phases'])

    def test_every_style_draws(self):
        for sid, _label, draw in TIMELINE_STYLES:
            with self.subTest(style=sid):
                pen, image = an_image_pen(900, 600)
                draw(pen, self.items, PALETTE, (10, 10, 890, 590))
                # Something besides the white background landed.
                colours = image.getcolors(maxcolors=1 << 24)
                self.assertGreater(len(colours), 8, sid)

    def test_render_timeline_with_nothing_flagged(self):
        pen, image = an_image_pen()
        render_timeline(pen, a_project(), 'lanes', PALETTE, 800, 600)
        # The empty state still drew - it is text over the background.
        self.assertGreater(len(image.getcolors(maxcolors=1 << 24)), 2)

    def test_an_unknown_style_falls_back_to_lanes(self):
        pen, image = an_image_pen()
        render_timeline(pen, self.project, 'nonsense', PALETTE, 800, 600)
        self.assertGreater(len(image.getcolors(maxcolors=1 << 24)), 8)


class TestTheTimeAxis(unittest.TestCase):
    """The shared column arithmetic the timeline styles sit on."""

    def test_a_short_plan_gets_month_columns(self):
        columns, step = axis_columns(BASE, BASE + timedelta(days=90), 900)
        self.assertEqual(step, 1)
        self.assertTrue(columns)
        self.assertTrue(all(col['x1'] > col['x0'] for col in columns))

    def test_a_long_plan_gets_year_columns(self):
        columns, step = axis_columns(
            BASE, BASE + timedelta(days=365 * 6), 900)
        self.assertGreaterEqual(step, 3)

    def test_columns_cover_the_span(self):
        end = BASE + timedelta(days=200)
        columns, _ = axis_columns(BASE, end, 900)
        self.assertLessEqual(columns[0]['x0'], 0)
        self.assertGreaterEqual(columns[-1]['x1'], 900 - 1)

    def test_span_is_padded(self):
        items = timeline_items(a_project(flag={'t2'}))
        start, end = timeline_span(items)
        self.assertLess(start, BASE)


class TestTheExports(unittest.TestCase):
    """PNG and PDF files actually written, through the PIL pipeline."""

    def setUp(self):
        self.project = a_project(flag={'t1', 't2', 't3', 't5'})
        self.tmp = tempfile.mkdtemp()

    def path(self, name):
        return os.path.join(self.tmp, name)

    def test_dashboard_png(self):
        from gantt_app.utils.image_export import export_dashboard_to_png
        out = self.path('dashboard.png')
        self.assertTrue(export_dashboard_to_png(
            self.project, out, boardrender.all_panel_ids()))
        from PIL import Image
        with Image.open(out) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertGreater(image.width, 1000)

    def test_dashboard_pdf(self):
        from gantt_app.utils.image_export import export_dashboard_to_pdf
        out = self.path('dashboard.pdf')
        self.assertTrue(export_dashboard_to_pdf(
            self.project, out, ['progress', 'summary']))
        with open(out, 'rb') as handle:
            self.assertEqual(handle.read(5), b'%PDF-')

    def test_dashboard_export_of_a_maximized_panel(self):
        """What you see is what you get - one panel, alone."""
        from gantt_app.utils.image_export import export_dashboard_to_png
        out = self.path('one.png')
        self.assertTrue(export_dashboard_to_png(
            self.project, out, ['progress', 'donut'],
            maximized_id='donut'))

    def test_timeline_png_in_each_style(self):
        from gantt_app.utils.image_export import export_timeline_to_png
        for sid, _label, _draw in TIMELINE_STYLES:
            with self.subTest(style=sid):
                out = self.path(f'tl_{sid}.png')
                self.assertTrue(export_timeline_to_png(
                    self.project, out, style_id=sid))
                self.assertGreater(os.path.getsize(out), 500)

    def test_timeline_pdf(self):
        from gantt_app.utils.image_export import export_timeline_to_pdf
        out = self.path('timeline.pdf')
        self.assertTrue(export_timeline_to_pdf(
            self.project, out, style_id='roadmap'))
        with open(out, 'rb') as handle:
            self.assertEqual(handle.read(5), b'%PDF-')


# -- the widget side needs a display -----------------------------------------

def _have_display():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
        return True
    except Exception:
        return False

HAVE_DISPLAY = _have_display()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheDashboardShell(unittest.TestCase):
    """The checklist, the cap and maximizing, on a real frame (#66)."""

    def setUp(self):
        import customtkinter as ctk
        from gantt_app.views.project_dashboard import \
            ProjectDashboardFrame

        self.ctk = ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.saved = []
        self.frame = ProjectDashboardFrame(
            self.root, a_project(),
            on_panels_changed=self.saved.append)
        self.frame.canvas.configure(width=1200, height=800)
        self.frame.refresh()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _toggle(self, pid, on):
        """What a checklist tick does, straight through."""
        var = self.ctk.BooleanVar(value=not on)
        self.frame._toggle_panel(pid, var)

    def test_unticking_a_panel_takes_it_off(self):
        var = self.ctk.BooleanVar(value=True)
        var.set(False)
        self.frame._toggle_panel('donut', var)
        self.assertNotIn('donut', self.frame.enabled)
        self.assertEqual(self.saved[-1], self.frame.enabled)

    def test_the_last_panel_stays(self):
        """A dashboard with nothing on it answers no question."""
        for pid in list(self.frame.enabled)[1:]:
            var = self.ctk.BooleanVar(value=False)
            self.frame._toggle_panel(pid, var)
        var = self.ctk.BooleanVar(value=False)
        self.frame._toggle_panel(self.frame.enabled[0], var)
        self.assertEqual(len(self.frame.enabled), 1)

    def test_a_panel_past_the_cap_is_refused(self):
        """The cap bites when a registry outgrows the board (#66, #120)."""
        extras = [('extra%d' % i, 'An extra',
                   lambda *a: None) for i in range(MAX_PANELS)]
        boardrender.DASHBOARD_PANELS.extend(extras)
        try:
            # Filled to the cap, as a settings file holding them all
            # would have left it.
            self.frame.enabled = boardrender.sanitize_panel_ids(
                boardrender.all_panel_ids())
            self.assertEqual(len(self.frame.enabled), MAX_PANELS)
            var = self.ctk.BooleanVar(value=True)
            self.frame._toggle_panel('extra1', var)
            self.assertNotIn('extra1', self.frame.enabled)
        finally:
            del boardrender.DASHBOARD_PANELS[-len(extras):]

    def test_maximize_and_restore(self):
        self.frame.set_maximized('summary')
        self.assertEqual(self.frame.maximized, 'summary')
        self.assertTrue(self.frame.restore_btn.winfo_ismapped()
                        or self.frame.restore_btn.winfo_manager())
        self.frame.restore()
        self.assertIsNone(self.frame.maximized)

    def test_maximizing_a_panel_that_is_off_does_nothing(self):
        self.frame.enabled = ['progress']
        self.frame.set_maximized('donut')
        self.assertIsNone(self.frame.maximized)


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class TestTheTimelineShell(unittest.TestCase):
    """The style picker on a real frame (issue #83)."""

    def setUp(self):
        import customtkinter as ctk
        from gantt_app.views.timeline_view import TimelineFrame

        self.ctk = ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.saved = []
        self.frame = TimelineFrame(
            self.root, a_project(flag={'t1', 't2'}),
            on_style_changed=self.saved.append)
        self.frame.canvas.configure(width=1200, height=700)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_it_starts_on_the_default_style(self):
        self.assertEqual(self.frame.style_id,
                         boardrender.DEFAULT_TIMELINE_STYLE)

    def test_picking_a_style_swaps_and_reports_it(self):
        self.frame.set_style('callouts')
        self.assertEqual(self.frame.style_id, 'callouts')
        self.assertEqual(self.saved[-1], 'callouts')
        self.assertIn('Callouts', self.frame.style_btn.cget('text'))

    def test_an_unknown_style_is_ignored(self):
        self.frame.set_style('nonsense')
        self.assertEqual(self.frame.style_id,
                         boardrender.DEFAULT_TIMELINE_STYLE)

    def test_a_saved_style_starts_the_frame(self):
        from gantt_app.views.timeline_view import TimelineFrame
        other = TimelineFrame(self.root, a_project(), style_id='phases')
        self.assertEqual(other.style_id, 'phases')
        other.destroy()


if __name__ == '__main__':
    unittest.main()

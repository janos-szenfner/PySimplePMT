Feature: Gantt chart figures and exports
  These exercise the figure builder and the exporters directly rather
  than through the GanttChart widget. The widget only wraps them, and
  building it needs a display, which made the suite slow and
  display-dependent.

  Static export is drawn with Pillow rather than handed to a browser, so
  every format runs everywhere with nothing downloaded and nothing
  installed.

  # -- The figure builder -----------------------------------------------

  Scenario: A project produces a Plotly figure with traces
    Given the sample export plan
    When a Gantt figure is built for it
    Then it is a Plotly figure holding traces

  Scenario: A project with no tasks still yields a usable figure
    Given an empty plan named "Empty"
    When a Gantt figure is built for it
    Then the figure's title reads "No tasks"

  Scenario: The y axis is reversed so the chart reads like the task list
    Given the sample export plan
    When a Gantt figure is built for it
    Then the y axis autorange is "reversed"

  Scenario: Y axis labels are the task names in start-date order
    Given the sample export plan
    When a Gantt figure is built for it
    Then the y axis labels are "Task 1", "Task 2" and "Review"

  Scenario: The chart title names the project
    Given the sample export plan
    When a Gantt figure is built for it
    Then the figure's title names "Export Test"

  Scenario: Caller settings override the defaults
    Given the sample export plan
    When a Gantt figure is built with a dark background and font size 20
    Then the paper background is "#101010" and the font size is 20

  Scenario: The date range extends beyond the first and last task
    Given the sample export plan
    When the figure's date range is calculated
    Then it starts before the first task and ends after the last

  Scenario: The empty-figure helper returns a figure with guidance
    When an empty figure is built
    Then it is a Plotly figure holding annotations

  # -- HTML export ---------------------------------------------------------

  Scenario: A standalone HTML file is written
    Given the sample export plan
    When the chart is exported as "chart.html"
    Then the file exists and holds more than 1000 bytes

  Scenario: The page loads nothing over the network
    Given the sample export plan
    When the chart is exported as "chart.html"
    Then no script tag loads from a remote source
    And the file holds more than a megabyte

  Scenario: A path with missing parents is created
    Given the sample export plan
    When the chart is exported as "nested/deeper/chart.html"
    Then the file exists

  Scenario: An empty project still produces a page
    Given an empty plan named "Empty"
    When the chart is exported as "empty.html"
    Then the file exists

  # -- Static export --------------------------------------------------------

  Scenario: A PNG file is produced
    Given the sample export plan
    When the chart is exported as "chart.png"
    Then the file exists and holds more than 1000 bytes

  Scenario: A PDF file is produced
    Given the sample export plan
    When the chart is exported as "chart.pdf"
    Then the file exists and holds more than 1000 bytes

  Scenario: A scalable SVG file is produced
    Given the sample export plan
    When the chart is exported as "chart.svg"
    Then the file starts with "<svg" and ends with "</svg>"

  Scenario: An empty project exports without error
    Given an empty plan named "Empty"
    When the chart is exported as "empty.png"
    Then the file exists

  Scenario: Export needs only Pillow, which the bundle always carries
    Then static export is available

  Scenario: Every format is produced offline
    Given the sample export plan
    When all four formats are exported with the network blocked
    Then every export succeeded

  # -- The renderer ---------------------------------------------------------

  Scenario: Each task gets a bar or a milestone marker
    Given the sample export plan
    When the chart is laid out
    Then every task has a bar or marker and a row label

  Scenario: Rows run top to bottom in start-date order
    Given the sample export plan
    When the chart is laid out
    Then the row labels are in order

  Scenario: Dependency lines are produced for each edge
    Given the sample export plan
    When the chart is laid out
    Then one dependency line exists per edge

  Scenario: An empty project yields a message instead of rows
    Given an empty plan named "Empty"
    When the chart is laid out
    Then the layout holds an empty message and no bars

  Scenario: A longer plan produces a taller image
    Given the sample export plan
    When ten extra tasks are added and both plans are rendered
    Then the bigger plan's image is taller

  Scenario: A task name containing markup cannot break the document
    Given a plan holding a task named "Fix <script> & \"quotes\""
    When the plan is rendered as SVG
    Then the SVG escapes the script and the ampersand

  Scenario: Font discovery answers without raising or downloading
    Then the font lookup returns a path or nothing

  # -- The width the chart is drawn at ---------------------------------------
  # The chart is drawn wider than its pane when a plan is long, so the
  # canvas scrolls sideways instead of squeezing every bar into the
  # visible space.

  Scenario: A short plan simply fills the pane
    Given a plan spanning 10 days
    Then its preferred width in a 1400-pixel pane is 1400

  Scenario: A cramped pane still gets a legible chart
    Given a plan spanning 10 days
    Then its preferred width in a 200-pixel pane is at least the minimum

  Scenario: A long plan overflows the pane so it can be scrolled
    Given a plan spanning 600 days
    Then its preferred width in a 800-pixel pane is more than 800

  Scenario: A multi-year plan cannot produce an unbounded image
    Given a plan spanning 5000 days
    Then its preferred width in a 800-pixel pane is at most the cap

  Scenario: With no tasks there is no span to accommodate
    Then an empty plan's preferred width in a 1400-pixel pane is 1400

  Scenario: The rendered image is the width that was asked for
    Given a plan spanning 600 days
    When it is rendered at its preferred width for a 800-pixel pane
    Then the image is that wide

  # -- The render budget -------------------------------------------------------
  # Dragging the pane divider redraws the chart, and each redraw hands a
  # fresh image to Tk, whose image memory Python does not collect. With no
  # ceiling on the image size a long plan produced hundreds of megabytes
  # per redraw, which was enough to lock up the machine.

  Scenario: An ordinary plan is drawn at full row height
    Given a plan holding 8 tasks over 60 days
    When the chart is laid out at 1400 pixels wide
    Then the rows are a full row height apart

  Scenario: A plan with hundreds of tasks stays within the pixel budget
    Given a plan holding 1000 tasks over 3000 days
    When the chart is laid out at 6000 pixels wide
    Then the layout is within the pixel budget

  Scenario: Rows are compressed rather than tasks being dropped
    Given a plan holding 1000 tasks over 3000 days
    When the chart is laid out at 6000 pixels wide
    Then every task still has a row label

  Scenario: The image handed to Tk is bounded, not just the layout
    Given a plan holding 1000 tasks over 3000 days
    When it is rendered at its preferred width for a 1400-pixel pane at scale 2
    Then the image is within the pixel budget

  Scenario: An unreasonable plan produces an image rather than failing
    Given a plan holding 3000 tasks over 3650 days
    When it is rendered at its preferred width for a 1400-pixel pane at scale 2
    Then the image is within the pixel budget
    And the image is wider than nothing

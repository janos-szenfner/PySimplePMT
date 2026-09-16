@pdf_pages
Feature: The pages of the exported PDF

  The export was one page of chart, which is half a plan: the bars say
  when work happens and nothing else - not what a row is called past
  the few characters that fit beside it, not how long it is, not what
  it waits for. Printed and handed round, that was a picture rather
  than a document.

  It is three pages now, and the things worth pinning down are the ones
  a reader would notice: that there are three, that each carries what
  it is meant to, and that the page is the physical size it claims to
  be. That last one is what made the old export print badly - a 2800
  pixel image saved at 150 dpi is a page eighteen inches wide, which
  every printer then shrank by an amount of its own choosing.

  The pages are compared as geometry and as content, never pixel by
  pixel: they are drawings, and pinning their pixels would fail on
  every deliberate change. The PDF itself is read back for its page
  boxes, which is the only way to know what a printer will be told.

  Background: a small plan with every kind of row in it
    Given the four-row rollout plan

  Scenario: There are three pages
    # The list beside the chart, the chart alone, and the full table.
    Then the plan renders 3 pages

  Scenario: They are all the same size
    # Or the PDF prints as three shapes rather than one document.
    Then every rendered page is the declared page size

  Scenario: A plan with no work still renders
    # An empty project is a document that says so, not a failure.
    Then an empty plan renders 3 pages

  Scenario: The table draws a row for every task
    # Height follows the row count, so the rows are all there.
    Then the task table is heading plus 4 rows tall

  Scenario: A page asking for fewer columns gets the right values
    # Columns are picked by key, not by position - paired by position,
    # a page showing five of the eight put Type under Start and
    # Duration under End.
    Then the cells for "003" carry every summary column
    And the cells for "003" read type "Subtask" and progress "60%"

  Scenario: The hierarchy is indented
    # A sub-task reads as one, the way it does in the window.
    Then the cell for "001" starts flush and "002" indented

  Scenario: A container shows the span it covers
    # Not the nought that duration_days answers for one - printed
    # beside two dates a fortnight apart, a nought says the phase takes
    # no time, which is the one thing it does not mean.
    Then the cell for "001" shows a non-zero duration

  Scenario: A milestone has no finish to show
    # It marks a moment, so the column says so rather than lying.
    Then the cell for "004" shows an em-dash end

  Scenario: A name too long for its column is trimmed
    # Measured, not counted: twenty narrow letters fit where twenty
    # wide ones do not.
    Then a long name is ellipsised inside 60 pixels

  Scenario: The file writes three pages
    # Read back out of the file rather than assumed.
    When the plan is exported to a PDF
    Then the file holds 3 MediaBoxes

  Scenario: Every page is the size it claims
    # A4 landscape in points. The old export saved a 2800 pixel image
    # at 150 dpi - a page eighteen inches wide - and every printer
    # shrank it by an amount of its own choosing.
    When the plan is exported to a PDF
    Then every MediaBox is within a tenth of an inch of the page size

  Scenario: It is landscape
    # A plan is wider than it is tall, and a portrait page wastes half
    # of itself.
    Then the declared page is wider than it is tall

  Scenario: An empty plan still writes a file
    # Exporting nothing is not an error.
    When an empty plan is exported to a PDF
    Then the written file is not empty

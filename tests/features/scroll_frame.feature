@scroll_frame
Feature: The scrolling container the task form is built in

  ScrollFrame replaced CTkScrollableFrame, whose scrollbar forces a
  full layout pass of the window on every draw. A replacement for
  something that worked has to be shown to work, so what the form
  actually relies on is checked here: that widgets put in it are
  inside the scrolling area, that the region follows the form as it
  grows, that the scrollbar comes and goes with the need for it, and
  that the wheel is given back when the pointer leaves.

  Scenario: Fields live inside the canvas
    # Fields go into content, which the canvas scrolls over. Gridding
    # into the ScrollFrame itself would put a field beside the
    # scrollbar and outside anything that scrolls.
    Given a window with a scrolling frame
    Then the content frame sits inside the canvas

  Scenario: The form is as wide as the canvas
    # A field set to stretch has the full width to stretch into. The
    # frame inside a canvas sits at its requested width unless it is
    # told otherwise, which would leave every field bunched to the
    # left.
    #
    # The resize is fired rather than waited for, and what the canvas
    # was told is what is checked. Tk delivers <Configure> from the
    # event queue, which update_idletasks does not run, and it re-lays
    # the frame inside the canvas out from the same queue - so a test
    # window that is never shown reaches neither on its own.
    Given a window with a scrolling frame
    When 2 rows of fields are put in and the canvas resizes to 400 wide
    Then the canvas holds the window 400 wide

  Scenario: A form that fits shows no scrollbar
    # All of it on show, so nothing to show a scrollbar for. Driven
    # through the callback the canvas fires with the slice of the form
    # on show - a window that is never mapped has no real height to
    # compare a form against.
    Given a window with a scrolling frame
    When the canvas reports the whole form on show
    Then no scrollbar is managed

  Scenario: A form that does not fit shows one
    # Half of it on show gets a scrollbar beside it.
    Given a window with a scrolling frame
    When the canvas reports the top half of the form on show
    Then the scrollbar is gridded in column 1

  Scenario: The scrollbar goes away again
    # A form that stops needing one stops showing one.
    Given a window with a scrolling frame
    When the canvas reports half then the whole form on show
    Then no scrollbar is managed

  Scenario: The region follows the form
    # The canvas scrolls over the whole form, however tall it has
    # grown. The region is worked out at the idle moment after a burst
    # of resizes, so this is what update_idletasks is settling.
    Given a window with a scrolling frame
    When 30 rows of fields are put in
    Then the scrollregion covers the form's height

  Scenario: The wheel is claimed when the pointer arrives
    # Entering the form binds the wheel to it.
    Given a window with a scrolling frame
    When the pointer arrives over the frame
    Then the wheel is bound application-wide

  Scenario: The wheel is given back when the pointer leaves
    # Leaving unbinds it, so the chart keeps its own wheel handling.
    # The pointer is nowhere near the withdrawn test window, so the
    # check finds it outside.
    Given a window with a scrolling frame
    When the pointer arrives and then leaves the frame
    Then the wheel is not bound application-wide

  Scenario: The wheel is given back when the frame goes
    # A destroyed form does not leave a binding behind pointing at it.
    Given a window with a scrolling frame
    When the pointer arrives and the frame is destroyed
    Then the wheel is not bound application-wide

  Scenario: A Windows notch moves one step
    # Windows sends multiples of 120, one notch at a time.
    Given a window with a scrolling frame
    When a wheel delta of -120 arrives over a scrollable form
    Then the canvas was asked to scroll 1 units

  Scenario: A macOS delta moves one step
    # macOS sends small numbers, whose sign is all that is read.
    Given a window with a scrolling frame
    When a wheel delta of 2 arrives over a scrollable form
    Then the canvas was asked to scroll -1 units

  Scenario: X11 buttons move either way
    # X11 sends Button-4 for up and Button-5 for down, with no delta.
    Given a window with a scrolling frame
    When wheel button 4 arrives over a scrollable form
    Then the canvas was asked to scroll -1 units
    When wheel button 5 arrives over a scrollable form
    Then the canvas was asked to scroll 1 units

  Scenario: A form that fits does not move
    # The wheel over a form with nothing to scroll leaves it alone.
    # The verdict is supplied rather than measured: an unmapped window
    # has no height to hold a form against.
    Given a window with a scrolling frame
    When a wheel delta of -120 arrives over a fitting form
    Then the canvas was asked nothing

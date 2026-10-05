Feature: The theme - who decides light or dark, and the colours that follow
  Two things are being pinned down and they fail in different ways.

  The controller fails loudly: a toggle that does not detach from the
  system, a sync that does not reattach, a poll that keeps running
  after the user has taken manual control.

  The palette fails silently, and worse. A colour written as one string
  is used in both appearances by CustomTkinter, so it looks right to
  whoever wrote it and is unreadable to half the people who use it.

  The toolbar control and the panes need a display and stay in the
  unittest module.

  # ---- following the desktop, or overriding it -----------------------------------------------

  Scenario: System mode takes the desktop's appearance
    # Which is the default, and the whole point of the mode.
    Given a controller over a "dark" desktop
    Then it follows the system
    And its appearance is "dark"
    And its mode is "system"

  Scenario: An explicit mode ignores the desktop
    # A light choice on a dark desktop stays light.
    Given a controller over a "dark" desktop in "light" mode
    Then its appearance is "light"
    And it does not follow the system

  Scenario: Toggling flips what is on screen
    # Pressing the button while following a dark desktop asks for light
    # - a manual light. Read off the mode instead, "system" is neither
    # light nor dark and there is nothing to flip.
    Given a controller over a "dark" desktop
    When it is toggled
    Then its appearance is "light"
    And its mode is "light"
    And it does not follow the system

  Scenario: Toggling twice returns to the appearance but not the mode
    # The user is still in manual control, which is what they asked for.
    Given a controller over a "dark" desktop
    When it is toggled
    And it is toggled
    Then its appearance is "dark"
    And its mode is "dark"
    And it does not follow the system

  Scenario: Syncing gives the decision back
    # And picks up whatever the desktop says now.
    Given a controller over a "dark" desktop
    When it is toggled
    And it syncs with the system
    Then it follows the system
    And its appearance is "dark"

  Scenario: An unknown mode is refused
    # Rather than guessed at, which would be a silent theme change.
    Given a controller over a "light" desktop
    When "sepia" mode is asked for
    Then the request is refused
    And its mode is "system"

  Scenario: The appearance is applied only when it changes
    # Reapplying it is a full redraw of every widget in the window.
    # Choosing "always dark" while already dark changes who decides,
    # not what is on screen.
    Given a controller over a "dark" desktop
    When "dark" mode is asked for
    Then it applied nothing

  # ---- the caption, the icon, and the status line ----------------------------------------------

  Scenario: It names the appearance it is in
    # A sun labelled Night would be nonsense.
    Then a "light" desktop says "Day"
    And a "dark" desktop says "Night"

  Scenario: The icon follows the appearance
    # Sun by day, moon by night.
    Then a "light" desktop carries the "sun" icon
    And a "dark" desktop carries the "moon" icon

  Scenario: Following the system says nothing
    # The default is the quiet case - a permanent "Following system"
    # badge is chrome nobody reads after the first day.
    Given a controller over a "light" desktop
    Then its status line is empty

  Scenario: A manual choice says so
    # Which is when it is telling the user something they may have
    # forgotten.
    Given a controller over a "light" desktop
    When it is toggled
    Then its status line mentions "Manual"

  # ---- the poll, and when it is allowed to run -----------------------------------------------------

  Scenario: System mode schedules a poll
    # Or the window never notices the desktop changing.
    Given a controller over a "light" desktop
    When it starts watching
    Then 1 poll is scheduled

  Scenario: An explicit mode schedules nothing
    # There is nothing for a poll to discover once the user has chosen.
    Given a controller over a "light" desktop in "dark" mode
    When it starts watching
    Then no polls are scheduled

  Scenario: Taking manual control stops the poll
    # And it is cancelled, not merely left to fire and do nothing - a
    # poll that goes on being rescheduled runs gsettings in a subprocess
    # on Linux for the life of the application.
    Given a controller over a "light" desktop
    And it is watching
    When it is toggled
    Then the poll is cancelled

  Scenario: Syncing again starts it back up
    # The window has to resume following the desktop.
    Given a controller over a "light" desktop
    And it is watching
    When it is toggled
    And it syncs with the system
    Then 2 polls have been scheduled

  Scenario: The window follows a desktop that changes
    # The behaviour the whole poll exists for.
    Given a controller over a "light" desktop
    And it is watching
    When the desktop turns "dark" and the poll fires
    Then it applied "dark"
    And its appearance is "dark"

  Scenario: A poll that finds nothing changes nothing
    # And still reschedules, or it would only ever follow once.
    Given a controller over a "light" desktop
    And it is watching
    When the poll fires
    Then it applied nothing
    And 2 polls have been scheduled

  # ---- telling the toolbar to redraw its control ------------------------------------------------------

  Scenario: A change reaches the listeners
    # With both halves: the mode and what it resolved to.
    Given a controller over a "light" desktop
    And a listener
    When it is toggled
    Then the listeners saw "dark:dark"

  Scenario: One failing listener does not stop the rest
    # A listener is a widget, and a destroyed widget raises when
    # written to. One dead toolbar must not keep the theme from
    # reaching the window.
    Given a controller over a "light" desktop
    And a failing listener
    And a listener
    When it is toggled
    Then the listener heard

  # ---- the preference: the choice has to outlive the process -------------------------------------------

  Scenario: A saved mode is read back
    # Which is what makes an override durable.
    When "dark" mode is saved
    Then it is saved
    And the mode read back is "dark"

  Scenario: No file means following the system
    # The right default to fall to.
    Given an empty settings directory
    Then the mode read back is "system"

  Scenario: An unreadable preference is not fatal
    # A preference is not worth failing to start over.
    Given a preference file holding "not json at all"
    Then the mode read back is "system"

  Scenario: A mode this version does not know is ignored
    # Rather than set, which would be an unreachable state.
    Given a preference file naming "sepia"
    Then the mode read back is "system"

  Scenario: A stand-in controller never writes
    # Or running the test suite changes the preference of whoever ran
    # it. A toolbar built without a controller makes one of its own,
    # and that controller belongs to nobody.
    Given a controller over a "light" desktop with saving watched
    When it is toggled
    And it syncs with the system
    Then nothing was saved

  Scenario: An owned controller does write
    # The preference is durable for the application that owns one.
    Given an owned controller over a "light" desktop with saving watched
    When it is toggled
    Then "dark" was saved once

  Scenario: An unwritable directory does not raise
    # The theme still works for this run; it just is not remembered.
    Given a settings directory that cannot be written
    Then saving "dark" returns False

  # ---- every colour is a pair ----------------------------------------------------------------------------

  Scenario: The list covers every pair in the module
    # The guard is only worth having while it is complete, and a pair
    # added without being listed here is exactly the colour that will
    # be wrong in one appearance.
    Then the palette lists every pair the module declares

  Scenario: Every entry has two halves
    # One colour is legible in one mode and not the other.
    Then every palette entry is a pair

  Scenario: The two halves differ
    # A pair of identical colours is a single colour with extra steps.
    Then no palette entry repeats itself

  Scenario: Every half is a colour
    # Catches a stray label or None finding its way in.
    Then every palette half is a six-figure hex colour

  Scenario: Pair refuses a single colour
    # The guard that says why, rather than failing in dark mode.
    Then pairing "#ffffff" raises

  Scenario: Resolve picks the right half
    # For the places that need a colour rather than a pair.
    Then "TEXT" resolves light to its first half and dark to its second

  # ---- contrast, measured rather than eyeballed ----------------------------------------------------------

  Scenario: Both appearances are readable
    # Light was; dark has to be too, which is the whole exercise. Every
    # text-on-background pair a reader has to be able to read is
    # measured against WCAG AA for body text.
    Then both appearances are readable

  Scenario: A disabled field is visibly quieter
    # It has to read as "not yours to fill in" without being
    # invisible: deliberately below the body-text ratio - that is what
    # makes it look inactive - but not so far below that it cannot be
    # read at all.
    Then the disabled field is quieter than a live one in both appearances

  # ---- the sun and the moon, drawn rather than fetched ------------------------------------------------------

  Scenario: Both icons are drawn
    # Nothing is bundled, so nothing can be missing at runtime.
    Then the "sun" and "moon" icons are drawn at 20px

  Scenario: They are drawn in the ink asked for
    # Two drawings per icon is what makes them visible in both
    # appearances. Handed the same near-black drawing for both, every
    # icon on the bar disappeared into the toolbar the moment the
    # window went dark.
    Then the "sun" drawn in light ink differs from dark ink

  Scenario: The moon is a crescent
    # A disc with a bite out of it, not a disc. The bite is taken by
    # writing transparent pixels over the disc, which is the only way
    # to get a crescent with no arc primitive - and it is the kind of
    # thing that silently becomes a full circle.
    Then the "moon" covers less than its disc but is not empty

  # ---- subscriptions do not pile up -----------------------------------------------------------------------
  # The controller belongs to the application and outlives its widgets.
  # A listener is normally a closure over a toolbar, so the controller
  # holding it holds the whole widget tree behind it.

  Scenario: A listener without an owner is kept
    # The old behaviour, for a caller that names none.
    Given a controller over a "light" desktop
    And an ownerless listener
    When it is toggled
    Then 1 listener is held

  Scenario: A listener goes when its owner does
    # Which is what stops the list growing for the life of the app.
    Given a controller over a "light" desktop
    And a listener owned by a widget
    When the owner dies
    And it is toggled
    Then no listeners are held

  Scenario: A dead listener is not called
    # Writing to a destroyed widget raises; it is dropped instead.
    Given a controller over a "light" desktop
    And a listener owned by a widget
    When the owner dies
    And it is toggled
    Then the listener heard nothing

  Scenario: A listener bound to a dead widget is not called either
    # The owner living does not mean the listener does: it may be a
    # bound method of a different widget that has been destroyed.
    Given a controller over a "light" desktop
    And a widget's bound method owned by something else
    When the widget dies
    And it is toggled
    Then the listener heard nothing
    And no listeners are held

  Scenario: Subscribing clears the ones that have gone
    # Rather than waiting for the next theme change - a toolbar being
    # rebuilt should clear the one it replaces, in an application whose
    # theme never moves, which is most of them.
    Given a controller over a "light" desktop
    And 5 subscriptions whose owners have died
    When a fresh listener subscribes
    Then 1 listener is held

  Scenario: A collected owner takes its listener with it
    # Held weakly, so an owner Tk never hears about still counts.
    Given a controller over a "light" desktop
    And a listener owned by a widget
    When the owner is collected
    And it is toggled
    Then no listeners are held

  Scenario: One can be detached by hand
    # For anything that has to go earlier than its owner.
    Given a controller over a "light" desktop
    And an ownerless listener
    When it is unsubscribed by hand
    Then the unsubscribe said so
    And unsubscribing it again says there was none
    And no listeners are held

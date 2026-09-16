@shortcuts
Feature: Which modifier key a shortcut uses, and what it is called

  Every shortcut in the application was written out as Control. On a
  Mac that is not the key anybody reaches for, and it is not the key
  macOS reports when they press Cmd - so the shortcuts did nothing
  there while their captions promised otherwise.

  The sequence and the caption are worked out from the same place
  because they have to agree. A caption naming a key that is not bound
  is worse than no caption at all, and the two drift the moment they
  are written separately.

  This is where the platform branch is pinned exactly. The tests that
  bind these cannot check the spelling: Tk stores a binding under a
  name of its own choosing - <Command-b> comes back as <Mod1-Key-b> -
  so those check only that something arrived for each key.

  Scenario: The modifier matches the platform
    # Command on a Mac, Control everywhere else.
    Then the modifier is Command on macOS and Control elsewhere

  Scenario: The label matches the modifier
    # What is shown and what is bound describe the same key.
    Then the label is the ⌘ symbol on macOS and Ctrl elsewhere

  Scenario: A letter is bound in both cases
    # Tk reports the upper case one when caps lock is on - a shortcut
    # that stops working with caps lock is the kind of fault nobody
    # reports and everybody notices.
    Then "b" binds two sequences, for "b" and "B"

  Scenario: The case it is given does not matter
    # A caller may pass either; both forms come back regardless.
    Then "B" binds the same sequences as "b"

  Scenario: A named key is bound once
    # Return has no case to worry about.
    Then "Return" binds one sequence for "Return"

  Scenario: Every sequence is shaped like one
    # A malformed sequence is a binding Tk refuses at run time.
    Then every sequence for "b", "Return" and "KP_Enter" is well formed

  Scenario: A Mac gets the symbol and no plus
    # ⌘B, which is how a Mac writes it.
    When the platform is a Mac
    Then the accelerator for "B" reads "⌘B"

  Scenario: Everywhere else gets Ctrl and a plus
    # Ctrl+B, which is how everywhere else writes it.
    When the platform is not a Mac
    Then the accelerator for "B" reads "Ctrl+B"

  Scenario: Return is written as Enter
    # Nobody calls the key Return on a keyboard.
    Then the accelerator for "Return" says Enter and not Return

  Scenario: It names the key that is actually bound
    # The caption and the binding come from the same branch. Written
    # separately they drift, and a caption promising a key that does
    # nothing is the fault this module exists to prevent.
    Then the accelerator for "B" matches the platform's modifier

  Scenario: The keysym is enough
    # The ordinary case, on every platform. Option is a compose key on
    # macOS: Option+I is the dead key for a circumflex, so the event
    # carries no 'i' anywhere a binding could match. All that is left
    # of the key pressed is where it sits on the keyboard.
    When an event carries keysym "i"
    Then it is the key "I"

  Scenario: Another key is not it
    # A near miss is still a miss.
    When an event carries keysym "o"
    Then it is not the key "I"

  Scenario: A packed keycode still names the key
    # The character underneath the keycode does not hide the key. Tk
    # packs the virtual keycode into the high bytes and leaves the
    # character below it, so the whole number is never equal to the
    # keycode on its own - which is what the comparison used to ask
    # for.
    When a Mac event carries the i keycode packed over a circumflex
    Then it is the key "I"

  Scenario: A bare keycode still names the key
    # The other spelling Tk has used for the same thing.
    When a Mac event carries the bare i keycode
    Then it is the key "I"

  Scenario: Another packed keycode is not it
    # A different physical key, packed the same way, is not I.
    When a Mac event carries the b keycode packed over a b
    Then it is not the key "I"

  Scenario: Both modifiers are held
    # The last net under the new-task shortcut: it has to catch
    # Cmd+Option+I.
    When a Mac event holds Command and Option
    Then the modifier pair is held

  Scenario: The modifier alone is not the pair
    # It must not catch plain Cmd+I - which is italic, and would start
    # creating tasks instead.
    When a Mac event holds Command alone
    Then the modifier pair is not held

  Scenario: A shift alongside does not matter
    # Other modifiers are not asked about.
    When a Mac event holds Command, Option and Shift
    Then the modifier pair is held

  Scenario: Nothing is read off a Mac
    # Everywhere else Tk matches the sequence, and the bit Alt sets is
    # not the same on Windows as on X11 - so this answers no rather
    # than guessing.
    When a non-Mac event holds Command and Option
    Then the modifier pair is not held

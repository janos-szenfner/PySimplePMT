@desktop_integration
Feature: The desktop entry and the application agree with each other

  The application installed from the .deb showed a generic cog rather
  than its own icon. Two things have to line up for a desktop to draw
  the right one, and neither of them is exercised by anything that runs
  the application:

    * the `Icon=` key names an icon that is installed under exactly that
      name, in a directory the icon theme looks in; and
    * `StartupWMClass` matches the WM_CLASS the window actually sets, or
      the desktop cannot tell which entry the running window belongs to
      and falls back to a generic icon in the dock and the switcher
      whatever the menu shows.

  The second was wrong: the entry declared `pysimplepmt` while Tk,
  given no class name, called every window `Tk` - the same as every
  other Tk application on the machine.

  The packaged files are read as text rather than installed, so the
  scenarios run anywhere. What they cannot check - that the files reach
  the right place inside the .deb - is checked by the release workflow
  against the installed package.

  Background: the desktop entry and the build script as shipped
    Given the packaged desktop entry and build script

  Scenario: The entry names an icon by a bare name
    # Not a path. The icon theme is keyed by name; a path bypasses the
    # theme, so the desktop cannot pick the size it wants and some
    # implementations ignore it outright.
    Then the Icon key is "pysimplepmt"
    And the Icon key is a bare name, not a path or a file

  Scenario: The package installs that icon
    # The build writes the name the entry asks for.
    Then the build script installs the hicolor and pixmaps icons

  Scenario: It is installed at every size the theme asks for
    # One 256 pixel file leaves menus scaling it down themselves. The
    # sizes are the ones the hicolor theme declares.
    Then the build script lists the seven hicolor sizes

  Scenario: The build refuses to ship without the icons
    # An icon nobody can see is a silent failure otherwise - the
    # launcher works, the menu entry appears, and it wears a cog.
    Then the build script checks the icons were written

  Scenario: It depends on the icon theme
    # Without hicolor-icon-theme the directory it installs into is not
    # a theme at all, and everything in it is ignored.
    Then the build script depends on hicolor-icon-theme

  Scenario: The categories are ones the menu knows
    # An unregistered category can have the entry filed nowhere.
    Then the Categories include Office and none are empty

  Scenario: The application sets a window class
    # Rather than leaving it as Tk, which everything else is called.
    Then the application declares WM_CLASS "pysimplepmt"

  Scenario: The entry declares the class Tk will produce
    # Tk capitalises the class name it is given, so the entry has to
    # name the capitalised form. Declaring the lower-case one matches
    # nothing.
    Then the StartupWMClass is the capitalised application class

  Scenario: The real window reports the declared class
    # Tk takes className when the interpreter is created and never
    # again, so a regression here can only be caught by building the
    # window. Needs a display.
    When the real application window is built
    Then the window's class matches the StartupWMClass

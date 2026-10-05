Feature: The update check reads the release feed (issue #41)
  The About window asks GitHub whether a newer release exists. The
  network is injected in these scenarios, so they check the version
  parsing, the comparison, and that a failure comes back as "unknown"
  rather than raising.

  # ---- version strings ------------------------------------------------

  Scenario Outline: Version text parses to numbers
    When the version "<text>" is parsed
    Then it reads as <major>.<minor>.<patch>

    Examples:
      | text          | major | minor | patch |
      | 1.68.2        | 1     | 68    | 2     |
      | v1.69.0       | 1     | 69    | 0     |
      | v1.69.0-beta2 | 1     | 69    | 0     |

  Scenario: A word that is not a version parses to nothing
    When the version "latest" is parsed
    Then no version is found

  Scenario: An empty tag parses to nothing
    When an empty version is parsed
    Then no version is found

  Scenario Outline: A higher release counts as newer
    When "<latest>" is compared against the running "<current>"
    Then newer is <answer>

    Examples:
      | latest  | current | answer |
      | 1.69.0  | 1.68.2  | yes    |
      | 1.68.2  | 1.68.2  | no     |
      | 1.68.1  | 1.68.2  | no     |
      | latest  | 1.68.2  | no     |

  # ---- asking the feed ------------------------------------------------

  Scenario: A newer release is an update
    Given the release feed answers tag "v1.69.0" at "https://example/rel"
    When the running "1.68.2" checks for an update
    Then the status is "update"
    And the latest version is "1.69.0"
    And the download page is "https://example/rel"

  Scenario: The same release means running the latest
    Given the release feed answers tag "v1.68.2" at "https://example/rel"
    When the running "1.68.2" checks for an update
    Then the status is "latest"

  Scenario: Running ahead of the release is not an update
    # A dev build ahead of the published release prompts nothing.
    Given the release feed answers tag "v1.68.2" at "https://example/rel"
    When the running "1.70.0" checks for an update
    Then the status is "latest"

  Scenario: A network error is unknown, not a crash
    Given the release feed is offline
    When the running "1.68.2" checks for an update
    Then the status is "unknown"
    And the info carries an error

  Scenario: A tag that is not a version is unknown
    Given the release feed answers tag "nightly" at "https://example/rel"
    When the running "1.68.2" checks for an update
    Then the status is "unknown"

  Scenario: Without a page URL it falls back to the releases page
    Given the release feed answers tag "v1.69.0" without a page
    When the running "1.68.2" checks for an update
    Then the status is "update"
    And the download page mentions "releases"

  Scenario: A latest 404 asks the releases list instead
    # releases/latest 404s while a release is still publishing.
    Given the latest call 404s and the list answers tag "v1.69.0"
    When the running "1.68.2" checks for an update
    Then the status is "update"
    And the latest version is "1.69.0"

  Scenario: A latest 404 with only drafts stays unknown
    Given the latest call 404s and the list has only drafts
    When the running "1.68.2" checks for an update
    Then the status is "unknown"

  Scenario: A list with a draft first skips to the real release
    # The fallback takes the first non-draft entry, not the first entry.
    Given the latest call 404s and the list leads with a draft then "v1.69.0"
    When the running "1.68.2" checks for an update
    Then the status is "update"
    And the latest version is "1.69.0"

  Scenario: A list answer that is not a list stays unknown
    Given the latest call 404s and the list answers a mapping
    When the running "1.68.2" checks for an update
    Then the status is "unknown"

  Scenario: A latest 404 with no releases at all stays unknown
    Given the latest call 404s and the list is empty
    When the running "1.68.2" checks for an update
    Then the status is "unknown"

  Scenario: A non-404 HTTP error is unknown
    Given the release feed answers HTTP 503
    When the running "1.68.2" checks for an update
    Then the status is "unknown"
    And the info carries an error

  Scenario: The release's downloadable assets come through
    # The About window hands the download step these assets; an asset
    # with no download URL is dropped rather than carried unusably.
    Given the release feed answers tag "v1.69.0" at "https://example/rel" carrying assets
    When the running "1.68.2" checks for an update
    Then the status is "update"
    And the info carries 1 downloadable asset
    And the asset is named "pysimplepmt-1.69.0-macos-arm64.dmg" from "https://example/dmg"

  # ---- the certificate store ------------------------------------------
  # The packaged build has no system CA store - the frozen macOS
  # interpreter never ran "Install Certificates" - so every HTTPS call
  # must verify against the certifi bundle the build ships, or the check
  # can only ever answer "couldn't check".

  Scenario: The fetch verifies against the bundled certifi store
    When the default fetch asks the release API
    Then the SSL context it used trusts the shipped certifi bundle

  Scenario: Without certifi the context still works
    When an SSL context is built without certifi
    Then it is still a usable SSL context

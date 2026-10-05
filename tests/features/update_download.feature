Feature: An assisted update brings down only what it can verify
  The release page carries one installer per platform plus a SHA256SUMS
  file. The assistant picks this platform's own asset, fetches the
  published digests, and refuses - removing the file - anything that
  does not match or cannot be checked. The network is injected, so
  these scenarios never touch it.

  # ---- picking the platform's installer -----------------------------

  Scenario: macOS takes the dmg
    Given the release offers "deb,dmg,sums"
    When an installer is picked for "darwin"
    Then the picked asset is the "dmg"

  Scenario: Linux takes the deb
    Given the release offers "deb,dmg,sums"
    When an installer is picked for "linux"
    Then the picked asset is the "deb"

  Scenario: Windows takes the msi
    Given the release offers "dmg,msi"
    When an installer is picked for "win32"
    Then the picked asset is the "msi"

  Scenario: Windows falls back to the exe
    Given the release offers "dmg,exe"
    When an installer is picked for "win32"
    Then the picked asset is the "exe"

  Scenario: An unknown platform gets nothing
    Given the release offers "dmg,deb"
    When an installer is picked for "sunos"
    Then nothing is picked

  Scenario: No matching asset picks nothing
    Given the release offers "deb,sums"
    When an installer is picked for "darwin"
    Then nothing is picked

  # ---- reading the SHA256SUMS listing -------------------------------

  Scenario: The digest of a listed file is found
    Given the standard checksums listing
    When the digest for "pysimplepmt-1.69.0-macos-arm64.dmg" is looked up
    Then the digest is "bbb222"

  Scenario: A file is matched on its basename
    Given the standard checksums listing
    When the digest for "/tmp/pysimplepmt_1.69.0_amd64.deb" is looked up
    Then the digest is "aaa111"

  Scenario: A binary marker is ignored
    Given a checksums line "deadbeef" for "pysimplepmt-1.69.0-macos-arm64.dmg" marked binary
    When the digest for "pysimplepmt-1.69.0-macos-arm64.dmg" is looked up
    Then the digest is "deadbeef"

  Scenario: An unlisted file finds nothing
    Given the standard checksums listing
    When the digest for "other.dmg" is looked up
    Then no digest is found

  # ---- download and verify ------------------------------------------

  Scenario: A matching checksum keeps the file
    Given a scratch folder
    And the download serves "the installer bytes"
    And a checksums listing digesting the payload for the "dmg" asset
    When the "dmg" asset is downloaded and verified
    Then the verified file is in the folder
    And the file's digest matches the payload's

  Scenario: A mismatched download is refused and removed
    # The bad file must not be left behind to be opened by hand.
    Given a scratch folder
    And the download serves "the installer bytes"
    And a checksums listing naming the "dmg" asset with a wrong digest
    When the "dmg" asset is downloaded and verified
    Then an integrity error is raised
    And the folder is empty

  Scenario: A file with no published checksum is refused
    Given a scratch folder
    And the download serves "the installer bytes"
    And a checksums listing naming "something-else.dmg" with digest "aaa"
    When the "dmg" asset is downloaded and verified
    Then an integrity error is raised

  Scenario: A failed download is reported as an update error
    Given a scratch folder
    And the download fails with "connection reset"
    And a checksums listing digesting the payload for the "dmg" asset
    When the "dmg" asset is downloaded and verified
    Then an update error is raised

  Scenario: A non-https asset URL is refused
    # The URL comes from an API response; urlopen would answer file:
    # or ftp: just as readily, so anything but https: is refused.
    Given a scratch folder
    And the download serves "the installer bytes"
    And a checksums listing digesting the payload for the "dmg" asset
    When the "dmg" asset at "file:///etc/passwd" is downloaded and verified
    Then an update error is raised
    And the folder is empty

  # ---- the whole fetch ----------------------------------------------

  Scenario: The verified installer comes down end to end
    Given a scratch folder
    And an update offering "dmg,sums"
    And the checksums fetch digests the payload "dmg-bytes" for the "dmg" asset
    And the download serves "dmg-bytes"
    When a verified installer is fetched for "darwin"
    Then the installer file is in the folder

  Scenario: A release without this platform's installer refuses
    Given a scratch folder
    And an update offering "sums"
    When a verified installer is fetched for "darwin"
    Then an update error is raised

  Scenario: A release without a checksums file refuses
    Given a scratch folder
    And an update offering "dmg"
    When a verified installer is fetched for "darwin"
    Then an integrity error is raised

  Scenario: Checksums over a non-https URL refuse
    Given a scratch folder
    And an update offering "dmg" with checksums fetched from "ftp://example/sums"
    When a verified installer is fetched for "darwin"
    Then an update error is raised

  Scenario: Assistance needs both a platform installer and the checksums
    Then a release of "dmg,sums" can assist "darwin"
    And a release of "dmg" cannot assist "darwin"
    And a release of "msi,sums" can assist "win32"

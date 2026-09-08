"""
A pixel reader that spans Pillow versions.

WHY THIS MODULE EXISTS:
======================
``Image.getdata()`` is deprecated from the Pillow release that renames it
``get_flattened_data()`` and is due for removal in Pillow 14. The new name
does not exist on the older Pillow the local development interpreter still
carries, so a straight swap would raise AttributeError there while the old
name warns on the newer Pillow the CI uses.

This prefers the new name when the installed Pillow has it and falls back to
the old one otherwise, so the tests read pixels without a deprecation warning
on new Pillow and without an error on old.
"""


def flat_pixels(image):
    """Every pixel of an image as a list, on any supported Pillow."""
    getter = getattr(image, "get_flattened_data", None) or image.getdata
    return list(getter())

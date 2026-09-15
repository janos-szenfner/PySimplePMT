"""
Priority levels for tasks.

WHY THIS MODULE EXISTS:
======================
Priority levels are used across the application and should be centralized
for consistency and easy modification.

DEVELOPMENT NOTES:
------------------
The scale has ten steps because levelling ranks work by it - five levels
left too many ties for the leveler to break, and a finer ladder lets a
plan say "delay this before that" with more precision than Low/Normal/High
ever allowed. The names follow the wording Microsoft Project documents
for its own priority bands.
"""

#: Available priority levels in order from lowest to highest.
#: Resource levelling delays the lower ones first; see core/leveling.py.
PRIORITY_LEVELS = (
    'Minimal',
    'Very Low',
    'Low',
    'Medium-Low',
    'Medium',
    'Medium-High',
    'High',
    'Very High',
    'Urgent',
    'Critical',
)

#: Default priority level
DEFAULT_PRIORITY = 'Medium'

#: What the retired five-step names mean on the ten-step ladder, so a plan
#: saved by an older version lands on the rung it meant rather than the
#: default.
LEGACY_PRIORITIES = {
    'Lowest': 'Minimal',
    'Low': 'Low',
    'Normal': 'Medium',
    'High': 'High',
    'Highest': 'Critical',
}


def normalize_priority(value) -> str:
    """
    The priority the value stands for on the current scale.

    A level the scale still carries passes through; a name the retired
    five-step scale used is translated; anything else - a blank, a number,
    a word nobody wrote - defaults.
    """
    text = str(value or '').strip()
    if text in PRIORITY_LEVELS:
        return text
    return LEGACY_PRIORITIES.get(text, DEFAULT_PRIORITY)


def priority_rank(value) -> int:
    """
    Where a priority sits on the ladder, lowest = 0.

    The leveler sorts by this, so an unknown name must not come back
    claiming to outrank everything - it ranks as the default, not -1.
    """
    return PRIORITY_LEVELS.index(normalize_priority(value))

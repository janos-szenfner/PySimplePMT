"""
Priority levels for tasks.

WHY THIS MODULE EXISTS:
======================
Priority levels are used across the application and should be centralized
for consistency and easy modification.
"""

#: Available priority levels in order from lowest to highest
PRIORITY_LEVELS = (
    'Lowest',
    'Low',
    'Normal',
    'High',
    'Highest',
)

#: Default priority level
DEFAULT_PRIORITY = 'Normal'

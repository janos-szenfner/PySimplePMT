"""
Domain model and scheduling logic for the Gantt Project Management Tool.

WHY THIS PACKAGE EXISTS:
=======================
Everything under here answers questions about the plan itself - what a task
is, which days count as working, how effort drives a schedule, what a
baseline measured - without ever touching a widget. Keeping that logic out
of ``views`` and ``utils`` means the scheduling rules can be exercised from
tests and importers without a window, and the window code never has to know
how the maths works.
"""

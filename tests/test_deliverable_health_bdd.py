"""
The health a deliverable's dates and progress say it has.

The scenarios live in features/deliverable_health.feature - issue #102's
row colours and the list-level roll-up. The board, its columns,
clipboard and menus need a display and stay in
tests/test_deliverables_board.py.
"""

from datetime import datetime, timedelta

from pytest_bdd import parsers, scenarios, then

from gantt_app.core.deliverable import (
    Deliverable, deliverable_health, overall_deliverable_health)


scenarios('features/deliverable_health.feature')


WHEN = {
    'yesterday': datetime.now() - timedelta(days=1),
    'tomorrow': datetime.now() + timedelta(days=1),
    'next week': datetime.now() + timedelta(days=7),
}


def _deliverable(deliverable_id='001', name='D', **kwargs):
    return Deliverable.create(name=name, deliverable_id=deliverable_id,
                              **kwargs)


# ---- one row ----------------------------------------------------------------------

@then(parsers.parse('a deliverable at {progress:d} reads "{health}"'))
def a_deliverable_at(progress, health):
    assert deliverable_health(
        _deliverable(progress=progress)) == health


@then(parsers.parse('a deliverable marked "{status}" due {when} reads '
                    '"{health}"'))
def a_marked_deliverable(status, when, health):
    assert deliverable_health(
        _deliverable(status=status, due_date=WHEN[when])) == health


@then(parsers.parse('a deliverable at {progress:d} due {when} reads '
                    '"{health}"'))
def a_deliverable_due(progress, when, health):
    assert deliverable_health(
        _deliverable(progress=progress, due_date=WHEN[when])) == health


@then(parsers.parse('an unstarted deliverable due {when} reads "{health}"'))
def an_unstarted_deliverable(when, health):
    assert deliverable_health(_deliverable(due_date=WHEN[when])) == health


# ---- the whole list ------------------------------------------------------------------

def _rows(spec):
    """A 'p=40 due yesterday | p=80' spec as a list of deliverables."""
    rows = []
    for index, piece in enumerate(spec.split('|'), 1):
        kwargs = {}
        for word in piece.strip().split(' due '):
            if word in WHEN:
                kwargs['due_date'] = WHEN[word]
            else:
                kwargs['progress'] = int(word.strip())
        rows.append(_deliverable(f'{index:03d}', **kwargs))
    return rows


@then(parsers.parse('deliverables "{spec}" read "{health}"'))
def the_list_reads(spec, health):
    assert overall_deliverable_health(_rows(spec)) == health


@then(parsers.parse('deliverables "{spec}" are not "{health}"'))
def the_list_is_not(spec, health):
    assert overall_deliverable_health(_rows(spec)) != health


@then(parsers.parse('no deliverables read "{health}"'))
def no_deliverables_read(health):
    assert overall_deliverable_health([]) == health
    assert overall_deliverable_health(None) == health

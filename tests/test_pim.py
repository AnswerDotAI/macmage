"""Contacts, calendars, and reminders against the real stores, so these need Imp's
`contacts`, `calendars`, and `reminders` grants. Creation tests clean up after themselves."""
from datetime import datetime, timedelta

from macmage import add_event, add_reminder, contacts, del_event, del_reminder, events, reminders

TITLE = 'macmage test item'


def test_contacts_search_runs():
    "A gibberish search returns nothing, but returns it without raising"
    assert contacts('zzqqxxyyverisimilitude') == []


def test_event_roundtrip():
    "An added event is listed with its fields, then removed"
    id = add_event(TITLE, datetime.now()+timedelta(days=1))
    try:
        ev = events(days=2).filter(lambda o: o['id']==id)[0]
        assert ev['title'] == TITLE and ev['end'] > ev['start']
    finally: del_event(id)
    assert not events(days=2).filter(lambda o: o['id']==id)


def test_reminder_roundtrip():
    "An added reminder is listed as open with its due date, then removed"
    due = datetime.now()+timedelta(days=1)
    id = add_reminder(TITLE, due=due)
    try:
        r = reminders().filter(lambda o: o['id']==id)[0]
        assert r['title'] == TITLE and not r['done'] and abs((r['due']-due).total_seconds()) < 60
    finally: del_reminder(id)
    assert not reminders().filter(lambda o: o['id']==id)

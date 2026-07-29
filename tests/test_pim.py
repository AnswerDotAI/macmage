"""Contacts, calendars, and reminders against the real stores, so these need Imp's
`contacts`, `calendars`, and `reminders` grants. Creation tests clean up after themselves."""
from datetime import datetime, timedelta

import cfloop
from macmage import add_event, add_reminder, contacts, del_event, del_reminder, events, reminders

TITLE = 'macmage test item'


def test_contacts_search_runs():
    "A gibberish search returns nothing, but returns it without raising"
    assert cfloop.run(contacts('zzqqxxyyverisimilitude')) == []


def test_event_roundtrip():
    "An added event is listed with its fields, then removed"
    async def main():
        id = await add_event(TITLE, datetime.now()+timedelta(days=1))
        try:
            ev = (await events(days=2)).filter(lambda o: o['id']==id)[0]
            assert ev['title'] == TITLE and ev['end'] > ev['start']
        finally: await del_event(id)
        assert not (await events(days=2)).filter(lambda o: o['id']==id)
    cfloop.run(main())


def test_reminder_roundtrip():
    "An added reminder is listed as open with its due date, then removed"
    async def main():
        due = datetime.now()+timedelta(days=1)
        id = await add_reminder(TITLE, due=due)
        try:
            r = (await reminders()).filter(lambda o: o['id']==id)[0]
            assert r['title'] == TITLE and not r['done'] and abs((r['due']-due).total_seconds()) < 60
        finally: await del_reminder(id)
        assert not (await reminders()).filter(lambda o: o['id']==id)
    cfloop.run(main())

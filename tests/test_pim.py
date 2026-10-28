"Create, find and remove calendar events and reminders through the real stores."
from datetime import datetime, timedelta

import cfloop
from macmage import add_event, add_reminder, del_event, del_reminder, events, reminders


def test_personal_information():
    async def story():
        title, due = 'macmage test item', datetime.now()+timedelta(days=1)
        id = await add_event(title, due)
        try:
            event = (await events(days=2)).filter(lambda o: o['id']==id)[0]
            assert event['title'] == title and event['end'] > event['start']
        finally: await del_event(id)
        assert not (await events(days=2)).filter(lambda o: o['id']==id)

        id = await add_reminder(title, due=due)
        try:
            reminder = (await reminders()).filter(lambda o: o['id']==id)[0]
            assert reminder['title'] == title and not reminder['done'] and abs((reminder['due']-due).total_seconds()) < 60
        finally: await del_reminder(id)
        assert not (await reminders()).filter(lambda o: o['id']==id)
    cfloop.run(story())

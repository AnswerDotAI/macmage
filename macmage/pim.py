"Contacts, calendars, and reminders, each needing its Imp permission"

import threading
from datetime import datetime, timedelta

from fastcore.utils import *
from Contacts import (CNContact, CNContactEmailAddressesKey, CNContactFamilyNameKey, CNContactGivenNameKey,
    CNContactOrganizationNameKey, CNContactPhoneNumbersKey, CNContactStore)
from EventKit import EKEvent, EKEventStore, EKReminder, EKSpanThisEvent
from Foundation import NSCalendar, NSCalendarUnitDay, NSCalendarUnitHour, NSCalendarUnitMinute, NSCalendarUnitMonth, NSCalendarUnitYear, NSDate

from fastcore.aio import athreaded
from .imp import need

__all__ = ['contacts', 'contact', 'events', 'add_event', 'del_event', 'reminders', 'add_reminder', 'del_reminder']

_ckeys = [CNContactGivenNameKey, CNContactFamilyNameKey, CNContactOrganizationNameKey,
    CNContactPhoneNumbersKey, CNContactEmailAddressesKey]


def _nsdate(dt): return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())
def _pydate(d): return datetime.fromtimestamp(d.timeIntervalSince1970()) if d is not None else None


def _cndict(c):
    name = f'{c.givenName()} {c.familyName()}'.strip() or str(c.organizationName())
    return dict(name=name, org=str(c.organizationName()), emails=[str(o.value()) for o in c.emailAddresses()],
        phones=[str(o.value().stringValue()) for o in c.phoneNumbers()])


@athreaded
def contacts(
    name:str # Name to match, as the Contacts search field would
):
    "Contacts matching `name`: dicts of name, org, phones, and emails"
    need('contacts')
    pred = CNContact.predicateForContactsMatchingName_(name)
    res, err = CNContactStore.alloc().init().unifiedContactsMatchingPredicate_keysToFetch_error_(pred, _ckeys, None)
    if err is not None: raise RuntimeError(str(err))
    return L(res).map(_cndict)


async def contact(
    name:str # Name to match; the first match wins
):
    "The first contact matching `name`, or None"
    return first(await contacts(name))


def _evdict(e):
    return dict(id=str(e.eventIdentifier()), title=str(e.title()), start=_pydate(e.startDate()),
        end=_pydate(e.endDate()), cal=str(e.calendar().title()))


@athreaded
def events(
    days=7 # How far ahead to look
):
    "Calendar events from now to `days` ahead: dicts of id, title, start, end, and cal"
    need('calendars')
    s = EKEventStore.alloc().init()
    pred = s.predicateForEventsWithStartDate_endDate_calendars_(NSDate.date(), NSDate.dateWithTimeIntervalSinceNow_(days*86400), None)
    return L(s.eventsMatchingPredicate_(pred)).map(_evdict)


@athreaded
def add_event(
    title:str, # Event title
    start:datetime, # When it starts
    end:datetime=None, # When it ends; an hour after `start` if None
    notes:str=None # Optional notes body
):
    "Add an event to the default calendar, returning its id"
    need('calendars')
    s = EKEventStore.alloc().init()
    ev = EKEvent.eventWithEventStore_(s)
    ev.setTitle_(title)
    ev.setStartDate_(_nsdate(start))
    ev.setEndDate_(_nsdate(end or start+timedelta(hours=1)))
    ev.setCalendar_(s.defaultCalendarForNewEvents())
    if notes: ev.setNotes_(notes)
    ok, err = s.saveEvent_span_error_(ev, EKSpanThisEvent, None)
    if not ok: raise RuntimeError(str(err))
    return str(ev.eventIdentifier())


@athreaded
def del_event(
    id:str # An id from `events` or `add_event`
):
    "Remove an event from its calendar"
    need('calendars')
    s = EKEventStore.alloc().init()
    ev = s.eventWithIdentifier_(id)
    if ev is None: raise ValueError(f'no event {id}')
    ok, err = s.removeEvent_span_error_(ev, EKSpanThisEvent, None)
    if not ok: raise RuntimeError(str(err))


def _rmdict(r):
    due = r.dueDateComponents()
    return dict(id=str(r.calendarItemIdentifier()), title=str(r.title()), done=bool(r.isCompleted()),
        due=_pydate(NSCalendar.currentCalendar().dateFromComponents_(due)) if due is not None else None)


@athreaded
def reminders(
    done:bool=False # Completed ones instead of open ones?
):
    "Reminders across all lists: dicts of id, title, done, and due"
    need('reminders')
    s = EKEventStore.alloc().init()
    got, evt = [], threading.Event()
    def cb(rs):
        got.extend(rs or [])
        evt.set()
    s.fetchRemindersMatchingPredicate_completion_(s.predicateForRemindersInCalendars_(None), cb)
    if not evt.wait(10): raise TimeoutError('EventKit did not answer')
    return L(got).filter(lambda r: bool(r.isCompleted())==done).map(_rmdict)


@athreaded
def add_reminder(
    title:str, # Reminder title
    due:datetime=None, # Optional due date
    notes:str=None # Optional notes body
):
    "Add a reminder to the default list, returning its id"
    need('reminders')
    s = EKEventStore.alloc().init()
    r = EKReminder.reminderWithEventStore_(s)
    r.setTitle_(title)
    r.setCalendar_(s.defaultCalendarForNewReminders())
    if notes: r.setNotes_(notes)
    if due:
        units = NSCalendarUnitYear|NSCalendarUnitMonth|NSCalendarUnitDay|NSCalendarUnitHour|NSCalendarUnitMinute
        r.setDueDateComponents_(NSCalendar.currentCalendar().components_fromDate_(units, _nsdate(due)))
    ok, err = s.saveReminder_commit_error_(r, True, None)
    if not ok: raise RuntimeError(str(err))
    return str(r.calendarItemIdentifier())


@athreaded
def del_reminder(
    id:str # An id from `reminders` or `add_reminder`
):
    "Remove a reminder from its list"
    need('reminders')
    s = EKEventStore.alloc().init()
    r = s.calendarItemWithIdentifier_(id)
    if r is None: raise ValueError(f'no reminder {id}')
    ok, err = s.removeReminder_commit_error_(r, True, None)
    if not ok: raise RuntimeError(str(err))

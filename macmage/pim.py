"Contacts, calendars, and reminders, each needing its Imp permission"

from datetime import datetime, timedelta

from fastcore.utils import *
from fastcore.aio import athreaded
from fastcocoa import wait_cb
from fastcocoa.contacts import (CNContact, CNContactEmailAddressesKey, CNContactFamilyNameKey, CNContactGivenNameKey,
    CNContactOrganizationNameKey, CNContactPhoneNumbersKey, CNContactStore)
from fastcocoa.eventkit import EKEvent, EKEventStore, EKReminder
from fastcocoa.foundation import NSCalendar, NSCalendarUnitDay, NSCalendarUnitHour, NSCalendarUnitMinute, NSCalendarUnitMonth, NSCalendarUnitYear, NSDate

from .imp import need

__all__ = ['contacts', 'contact', 'events', 'add_event', 'del_event', 'reminders', 'add_reminder', 'del_reminder']

_ckeys = [CNContactGivenNameKey, CNContactFamilyNameKey, CNContactOrganizationNameKey,
    CNContactPhoneNumbersKey, CNContactEmailAddressesKey]


def _cndict(c):
    name = f'{c.givenName} {c.familyName}'.strip() or c.organizationName
    return dict(name=name, org=c.organizationName, emails=[o.value for o in c.emailAddresses],
        phones=[o.value.stringValue for o in c.phoneNumbers])


@athreaded
def contacts(
    name:str # Name to match, as the Contacts search field would
):
    "Contacts matching `name`: dicts of name, org, phones, and emails"
    need('contacts')
    pred = CNContact.predicateForContacts(matchingName=name)
    return CNContactStore().unifiedContacts(matching=pred, keysToFetch=_ckeys).map(_cndict)


async def contact(
    name:str # Name to match; the first match wins
):
    "The first contact matching `name`, or None"
    return first(await contacts(name))


def _evdict(e): return dict(id=e.eventIdentifier, title=e.title, start=e.startDate, end=e.endDate, cal=e.calendar.title)


@athreaded
def events(
    days=7 # How far ahead to look
):
    "Calendar events from now to `days` ahead: dicts of id, title, start, end, and cal"
    need('calendars')
    s = EKEventStore()
    pred = s.predicateForEvents(startDate=NSDate.date(), endDate=NSDate(timeIntervalSinceNow=days*86400), calendars=None)
    return s.events(matching=pred).map(_evdict)


@athreaded
def add_event(
    title:str, # Event title
    start:datetime, # When it starts
    end:datetime=None, # When it ends; an hour after `start` if None
    notes:str=None # Optional notes body
):
    "Add an event to the default calendar, returning its id"
    need('calendars')
    s = EKEventStore()
    ev = EKEvent(eventStore=s, title=title, startDate=start, endDate=end or start+timedelta(hours=1), calendar=s.defaultCalendarForNewEvents)
    if notes: ev.notes = notes
    s.save(ev, span='thisEvent')
    return ev.eventIdentifier


@athreaded
def del_event(
    id:str # An id from `events` or `add_event`
):
    "Remove an event from its calendar"
    need('calendars')
    s = EKEventStore()
    ev = req(s.eventWithIdentifier(id), f'no event {id}')
    s.remove(ev, span='thisEvent')


def _rmdict(r):
    due = r.dueDateComponents
    return dict(id=r.calendarItemIdentifier, title=r.title, done=r.completed,
        due=NSCalendar.currentCalendar().dateFromComponents(due) if due is not None else None)


@athreaded
def reminders(
    done:bool=False # Completed ones instead of open ones?
):
    "Reminders across all lists: dicts of id, title, done, and due"
    need('reminders')
    s = EKEventStore()
    got, = wait_cb(s.fetchReminders, matching=s.predicateForReminders(in_=None), completion=...)
    return (got or L()).filter(lambda r: r.completed==done).map(_rmdict)


@athreaded
def add_reminder(
    title:str, # Reminder title
    due:datetime=None, # Optional due date
    notes:str=None # Optional notes body
):
    "Add a reminder to the default list, returning its id"
    need('reminders')
    s = EKEventStore()
    r = EKReminder(eventStore=s, title=title, calendar=s.defaultCalendarForNewReminders)
    if notes: r.notes = notes
    if due:
        units = NSCalendarUnitYear|NSCalendarUnitMonth|NSCalendarUnitDay|NSCalendarUnitHour|NSCalendarUnitMinute
        r.dueDateComponents = NSCalendar.currentCalendar().components(units, fromDate=due)
    s.save(r, commit=True)
    return r.calendarItemIdentifier


@athreaded
def del_reminder(
    id:str # An id from `reminders` or `add_reminder`
):
    "Remove a reminder from its list"
    need('reminders')
    s = EKEventStore()
    r = req(s.calendarItemWithIdentifier(id), f'no reminder {id}')
    s.remove(r, commit=True)

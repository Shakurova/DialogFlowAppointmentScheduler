from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
from datetime import timedelta
import datefinder

from config import SERVICE_ACCOUNT_FILE, CALENDAR_ID, TIMEZONE_OFFSET, TIMEZONE

SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarClient:
    """
    Client for Google Calendar API.
    """

    def __init__(self, *args, **kwargs):
        self.credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        self.service = build("calendar", "v3", credentials=self.credentials)

    def _format_datetime(self, datetime_object):
        formatted_datetime = datetime_object.isoformat(timespec='seconds')
        if not datetime_object.utcoffset():
            formatted_datetime += TIMEZONE_OFFSET
        return formatted_datetime

    def show_upcoming_events(self, max_results=10):
        """
        Print next max_results events.
        """

        # Set current date and time
        now = datetime.datetime.utcnow().isoformat() + TIMEZONE_OFFSET

        # Getting the upcoming max_results events
        events_result = self.service.events().list(calendarId=CALENDAR_ID, timeMin=now,
                                            maxResults=max_results, singleEvents=True,
                                            orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            return 'No upcoming events found.'

        else:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(start, event['summary'])
            return [(event['start'], event['summary']) for event in events]


    def get_events(self, query, start_time_str=None, duration=1):
        """
        Get event given query and start time.
        """

        if start_time_str:
            matches = list(datefinder.find_dates(start_time_str))
            if len(matches):
                time_min = matches[0]
                time_max = time_min + timedelta(hours=duration)
                time_min = self._format_datetime(time_min)
                time_max = self._format_datetime(time_max)
                print(time_min, time_max)
        else:
            now = datetime.datetime.utcnow()
            time_delta = datetime.timedelta(days=30)
            time_min = self._format_datetime(now - time_delta)
            time_max = self._format_datetime(now + time_delta)
            print(time_min, time_max)

        events = self.service.events().list(calendarId=CALENDAR_ID,
                                        q=query,
                                        timeMin=time_min,
                                        timeMax=time_max,
                                        singleEvents=True,
                                        orderBy='startTime'
                                        ).execute()

        print(events.get('items', []))

        return events.get('items', [])

    def check_availablity(self, start_time_str, duration=1):
        response = []

        matches = list(datefinder.find_dates(start_time_str))
        if len(matches):
            start_time = matches[0]
            end_time = start_time + timedelta(hours=duration)

        if self.get_events(query=None, start_time_str=start_time_str, duration=1):
            response.append(f"I'm sorry, there are no slots available for {start_time_str}. Would some other time work for you?")
            return False, response
        else:
            response.append(f"Ok, let me see if we can fit you in.")
            response.append(f"{start_time_str} is fine!")
            return True, response

    def create_event(self, start_time_str, summary, duration=1, description=None, location=None):
        """
        Create event given start date, end date and title.
        """

        response = []

        matches = list(datefinder.find_dates(start_time_str))
        if len(matches):
            start_time = matches[0]
            end_time = start_time + timedelta(hours=duration)

        event = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                'timeZone': TIMEZONE,
            },
            'end': {
                'dateTime': end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                'timeZone': TIMEZONE,
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
         }

        print("*** %r event added: Start: %s End:   %s" % (summary.encode('utf-8'), start_time, end_time))
        self.service.events().insert(calendarId=CALENDAR_ID, body=event, sendNotifications=True).execute()

        response.append(f"The event has just been added to your calendar!")

        print("response", response)
        return response

    def delete_event(self, event_id):
        """
        Delete event given ID.
        """

        print(f"Deleting event with id: {event_id}")

        return self.service.events().delete(calendarId=CALENDAR_ID, eventId=event_id, sendNotifications=True).execute()


# if __name__ == "__main__":
#
#     calendar = GoogleCalendarClient()
#
#     calendar.show_upcoming_events()
#
#     calendar.create_event("2020-04-18 12:00:00", "Call with wiz")
#
#     event_id = calendar.get_events(query="Wiz")[0]["id"]
#     delete_event(event_id)
#
#     get_events(query="Wiz", start_time_str="2020-04-18 10:00:00")

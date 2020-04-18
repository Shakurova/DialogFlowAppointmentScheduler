import json
import os
import base64

from flask import Flask, request, make_response, jsonify, Response

import icalendar
from icalendar import vCalAddress, vText
from calendar_utils import GoogleCalendarClient

import datefinder
import datetime
from datetime import datetime
from datetime import timedelta

import sendgrid
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName,
    FileType, Disposition, ContentId)

from config import SENDGRID_API_KEY, MY_EMAIL, MY_NAME, TIMEZONE_OFFSET

app = Flask(__name__)
log = app.logger

@app.route('/', methods=['POST'])
def webhook():
    """
    This method handles the http requests for the Dialogflow webhook
    This is meant to be used in conjunction with the weather Dialogflow agent.
    """

    req = request.get_json(silent=True, force=True)

    try:
        intent = req.get('queryResult').get('intent').get('displayName')
    except AttributeError:
        return 'json error'

    res = "I'm sorry, didn't hear you. Could you repeat it please? "

    # Initiate Google Calendar class
    calendar = GoogleCalendarClient()

    if intent == 'Schedule Appointment':
        res = check_availablity(calendar, req)

    elif intent == 'Schedule Appointment - Email - Name':
        res = send_email(calendar, req)

    else:
        log.error('Unexpected intent.')

    log.info('Intent: ', intent)
    log.info('Response: ', res)

    messages = []
    if type(res) == list:
        for text in res:
            messages.append({"text": {"text": [text]}})
    else:
        messages = {"text": {"text": [text]}}

    js = {'fulfillmentMessages': messages}
    return Response(json.dumps(js),  mimetype='application/json')
    # return make_response(jsonify({'fulfillmentMessages': messages}))


def check_availablity(calendar, req):
    parameters = req['queryResult']['parameters']

    print('Dialogflow Parameters:')
    print(json.dumps(parameters, indent=4))

    start_date = parameters['date'].split('T')[0] + 'T' + parameters['time'].split('T')[1].split('+')[0] + TIMEZONE_OFFSET
    cal_resp = calendar.check_availablity(start_date)

    return cal_resp[1]


def send_email(calendar, req):
    parameters = req['queryResult']['parameters']

    given_name = parameters['given-name']
    email = req['queryResult']['outputContexts'][0]['parameters']['email']
    date = req['queryResult']['outputContexts'][1]['parameters']['date']
    time = req['queryResult']['outputContexts'][1]['parameters']['time']

    print("Parameters:", given_name, email, date, time)

    # Get dates
    start_date = date.split('T')[0] + 'T' + time.split('T')[1].split('+')[0] + TIMEZONE_OFFSET
    matches = list(datefinder.find_dates(start_date))[0]
    end_date = str(matches + timedelta(hours=1))

    # Create SendGrid email
    message_request = Mail(
        from_email=MY_EMAIL,
        to_emails=MY_EMAIL,
        subject="Appointment request from " + MY_NAME,
        html_content="Hey, Lena!<br> " + given_name + " just sent an appointment request for " + start_date + ". <br>Please send an email of confirmation to " + email)

    message_confirmation = Mail(
        from_email=MY_EMAIL,
        to_emails=email,
        subject="Appointment confirmation with " + MY_NAME,
        html_content="Hey, " + given_name + "! <br> " + MY_NAME + " just received your appointment request for " + start_date + " and will contact you soon. <br> Meanwhile, please add the event to your calendar.")

    appointment = create_event(start_date, end_date, given_name, email)
    encoded = base64.b64encode(appointment).decode()
    attachment = Attachment()
    attachment.file_content = FileContent(encoded)
    attachment.file_type = FileType('text/calendar')
    attachment.file_name = FileName('appointment.ics')
    attachment.disposition = Disposition('attachment')
    attachment.content_id = ContentId('testID')

    message_request.attachment = attachment
    message_confirmation.attachment = attachment

    try:
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)

        # Message Request
        response = sg.send(message_request)
        print(response.status_code)
        print(response.body)
        print(response.headers)

        # Message Confirmation
        response = sg.send(message_confirmation)
        print(response.status_code)
        print(response.body)
        print(response.headers)

        return 'Thank you, ' + given_name + ' . I just sent you an email to' + email + '!'

    except Exception as e:
        print(e.message)
        return 'Sorry, something went wrong :('


def create_event(start_date, end_date, given_name, email):

    # Create calendar
    vcal = icalendar.Calendar()
    vcal.add('prodid', '-//My calendar//shakurova.io//EN')
    vcal.add('version', '2.0')
    vcal.add('method', 'REQUEST')
    vcal.add('name', 'Lena')

    # Create event
    event = icalendar.Event()
    start_date = list(datefinder.find_dates(start_date))[0]
    end_date = list(datefinder.find_dates(end_date))[0]
    event.add('dtstart', start_date)
    event.add('dtend', end_date)
    event['dtstart'] = event['dtstart'].to_ical()
    event['dtend'] = event['dtend'].to_ical()

    # Add event information
    event.add('summary', 'Online meeting with ' + MY_NAME)
    event.add('location', 'Online via zoom')
    event.add('description', 'Online meeting with ' + MY_NAME + ' to discuss chatbot development.')
    event.add('priority', 5)

    # # Add organiser
    # organizer = vCalAddress("MAILTO:" + MY_EMAIL)
    # organizer.params["cn"] = vText(MY_NAME)
    # event.add('organizer', organizer, encode=0)

    # Add attendee
    attendee = vCalAddress("MAILTO:" + MY_EMAIL)
    attendee.params['cn'] = vText(MY_NAME)
    attendee.params['ROLE'] = vText('REQ-PARTICIPANT')
    attendee.params['RSVP'] = vText(str(bool(True)).upper())
    event.add('attendee', attendee, encode=0)

    # Add attendee
    attendee = vCalAddress('MAILTO:' + email)
    attendee.params['cn'] = vText(given_name)
    attendee.params['ROLE'] = vText('REQ-PARTICIPANT')
    attendee.params['RSVP'] = vText(str(bool(True)).upper())
    event.add('attendee', attendee, encode=0)

    vcal.add_component(event)

    print("ICS file: \n", vcal.to_ical())

    return vcal.to_ical()

if __name__ == '__main__':
    app.run(debug=True, port=4004)

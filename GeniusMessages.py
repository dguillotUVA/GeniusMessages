from apiclient import errors, discovery
import base64
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import html2text
import httplib2
import json
import oauth2client
from oauth2client import client, tools
import os
import pyodbc
import time


path = os.path.dirname(os.path.realpath(__file__))
settings_file = os.path.join(path, 'settings.txt')
user_file = os.path.join(path, 'users.txt')
error_file = os.path.join(path, 'error_log.txt')
log_file = os.path.join(path, 'logs.txt')

with open(settings_file, 'r') as f:
	settings = json.load(f)

direct_ip = settings["Direct IP"]

sender = "No-reply@uview.academy"

SCOPES = 'https://www.googleapis.com/auth/gmail.send'
CLIENT_SECRET_FILE = 'credentials.json'
APPLICATION_NAME = 'Gmail API Python Send Email'

def get_credentials():
	home_dir = os.path.expanduser('~')
	credential_dir = os.path.join(home_dir, '.credentials')
	if not os.path.exists(credential_dir):
		os.makedirs(credential_dir)
	credential_path = os.path.join(credential_dir, 'gmail-python-email-send.json')
	store = oauth2client.file.Storage(credential_path)
	credentials = store.get()
	if not credentials or credentials.invalid:
		flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
		flow.user_agent = APPLICATION_NAME
		credentials = tools.run_flow(flow, store)
		print('Storing credentials to ' + credential_path)
	return credentials

def SendMessage(sender, to, subject, msgHtml, msgPlain):
	credentials = get_credentials()
	http = credentials.authorize(httplib2.Http())
	service = discovery.build('gmail', 'v1', http=http)
	message1 = CreateMessage(sender, to, subject, msgHtml, msgPlain)
	SendMessageInternal(service, "me", message1)

def SendMessageInternal(service, user_id, message):
	try:
		message = (service.users().messages().send(userId=user_id, body=message).execute())
		print('Message Id: %s' % message['id'])
		return message
	except errors.HttpError as error:
		print('An error occurred: %s' % error)

def CreateMessage(sender, to, subject, msgHtml, msgPlain):
	msg = MIMEMultipart('alternative')
	msg['Subject'] = subject
	msg['From'] = sender
	msg['To'] = to
	msg.attach(MIMEText(msgPlain, 'plain'))
	msg.attach(MIMEText(msgHtml, 'html'))
	raw = base64.urlsafe_b64encode(msg.as_bytes())
	raw = raw.decode()
	body = {'raw': raw}
	return body

def full_genius_messages(direct_ip, users, cursor, logs):
	print(str(datetime.datetime.now()) + " Starting message cylce.")

	last_max_msg_index = logs["Last Full Message Index"]

	user_list = ""
	for x in users: #Generate user_list string for SQL Query
		user_list += "{},".format(x)
	user_list = user_list[:-1]

	print("Querying database.")
	cursor.execute("SELECT MESSAGEINDEX, USERINDEX, SENDER, SUBJECT, CONTENTS, SENDTIME FROM OPENQUERY([{}],'SELECT mr.UserIndex, CONCAT(Users.FirstName, '' '', Users.LastName) AS Sender, Subject, Contents, DateTime AS SendTime, mes.MessageIndex FROM Messages mes INNER JOIN MessageRecipients mr ON mes.MessageIndex = mr.MessageIndex INNER JOIN Users ON Users.UserIndex = mes.SenderUserIndex WHERE mr.UserIndex IN ({}) AND mr.ReadOn IS NULL AND mes.MessageIndex > {}')".format(direct_ip, user_list, last_max_msg_index))
	rows = cursor.fetchall()

	print("Sending full messages.")

	for row in rows:
		message_index = row[0]
		user_index = str(row[1])
		message_sender = row[2]
		subject = "[Genius Message]: " + row[3]
		contents = row[4]
		send_time = row[5]
		message_html = "The following message was sent to you in Genius. <b><i>Responses should be sent in Genius</b></i>.<br>Sender: {}<br>Time: {}<br>Subject: {}<br><br>".format(message_sender, send_time, subject) + contents
		to = users[user_index]["Email"]
		message_plain = html2text.html2text(message_html)
		SendMessage(sender, to, subject, message_html, message_plain)
		if message_index > last_max_msg_index:
			last_max_msg_index = message_index
		time.sleep(1)
		
	print("Updating local data.")
	logs["Last Full Run"] = str(datetime.datetime.now())
	logs["Last Full Message Index"] = last_max_msg_index
	with open(log_file, 'w+') as f:
		f.write(json.dumps(logs))

	return cursor, logs

def simple_notifications(direct_ip, users, cursor, logs):
	print(str(datetime.datetime.now()) + " Starting notification cycle.")

	user_list = ""
	for x in users: #Generate user_list string for SQL Query
		user_list += "{},".format(x)
	user_list = user_list[:-1]

	last_max_msg_index = int(logs["Last Simple Message Index"])

	print("Querying database.")
	cursor.execute("SELECT USERINDEX, MOSTRECENTMESSAGE, UNREADMESSAGES FROM OPENQUERY([{}],'SELECT mr.UserIndex, MAX(mr.MessageIndex) AS MostRecentMessage, COUNT(mr.MessageIndex) AS UnreadMessages FROM MessageRecipients mr WHERE UserIndex IN ({}) AND mr.MessageIndex > {} AND ReadOn IS NULL GROUP BY mr.UserIndex')".format(direct_ip, user_list, last_max_msg_index))
	rows = cursor.fetchall()
	
	print("Sending simple messages.")

	for row in rows:
		user_index = str(row[0])
		current_message_index = row[1]
		unread_count = row[2]
		to = users[user_index]["Email"]
		subject = "New Genius Message(s)"
		message_html = "You have {} new Genius message(s).<br>This is an automated message. This mailbox is not monitored, so please do not reply to this message.".format(unread_count)
		message_plain = html2text.html2text(message_html)
		SendMessage(sender, to, subject, message_html, message_plain)
		if current_message_index > last_max_msg_index:
			last_max_msg_index = current_message_index
		time.sleep(1)

	print("Updating local data.")
	logs["Last Simple Run"] = str(datetime.datetime.now())
	logs["Last Simple Message Index"] = last_max_msg_index
	with open(log_file, 'w+') as f:
		f.write(json.dumps(logs))

	return cursor, logs

def enroll_check(direct_ip, cursor, logs, user_file, users):
	print("Updating user list.")

	last_max_msg_index = logs["Last Enroll Message Index"]

	cursor.execute("SELECT MESSAGEINDEX, USERINDEX, SENDER, SUBJECT, PRIVILEGE, EMAIL FROM OPENQUERY([{}],'SELECT mes.MessageIndex, mr.UserIndex, CONCAT(Users.FirstName, '' '', Users.LastName) AS Sender, Subject, Privilege, Email FROM Messages mes INNER JOIN MessageRecipients mr ON mes.MessageIndex = mr.MessageIndex INNER JOIN Users ON Users.UserIndex = mes.SenderUserIndex INNER JOIN (SELECT MAX(mes.MessageIndex) AS MessageIndex, mr.UserIndex FROM Messages mes INNER JOIN MessageRecipients mr ON mes.MessageIndex = mr.MessageIndex INNER JOIN Users ON Users.UserIndex = mes.SenderUserIndex WHERE mr.UserIndex = mes.SenderUserIndex AND Users.Privilege NOT IN (''student'', ''guardian'', ''coach'', ''inactive'') AND mes.Subject IN (''Email Subscribe Simple'', ''Email Subscribe Full'', ''Email Unsubscribe'') GROUP BY mr.UserIndex) Recent ON Recent.MessageIndex = mes.MessageIndex WHERE mes.MessageIndex > {}') ORDER BY MESSAGEINDEX".format(direct_ip,last_max_msg_index))
	rows = cursor.fetchall()

	for row in rows:
		if last_max_msg_index < row[0]:
			last_max_msg_index = row[0]
		user_id = str(row[1])
		if row[3].lower() == "email subscribe simple" or row[3].lower() == "email subscribe full":
			username = row[2]
			user_email = row[5]
			msg_type = row[3][16:]
			users[str(user_id)] = {"Name": username, "Email": user_email, "Type": msg_type}
			subject = "Genius Email Subscription"
			if row[3].lower() == "email subscribe simple":
				message_html = "You have subscribed to receive simple Genius notifications via email. Every 30 minutes, if you have new unready messages, you will receive an email notifications along with a count of new Genius messages. If you subscribed in error or no longer wish to receive these emails, please send a Genius message to yourself with the subject \"Email Unsubscribe\""
			elif row[3].lower() == "email subscribe full":
				message_html = "You have subscribed to receive an email copy of your unread Genius messages. Please note that <b><i>replies must be sent in Genius</b></i>. If you subscribed in error or no longer wish to receive these emails, please send a Genius message to yourself with the subject \"Email Unsubscribe\""
			to = users[str(user_id)]["Email"]
			message_plain = html2text.html2text(message_html)
			SendMessage(sender, to, subject, message_html, message_plain)

		elif row[3].lower() == "email unsubscribe":
			if str(user_id) in users:
				subject = "Genius Email: Unsubscribed"
				message_html = "You have unsubscribed from Genius notification emails. If you wish to subscribe again later, please send a Genius message to yourself with the subject \"Email Subscribe Simple\" to receive a 30 minute summary of new messages or \"Email Subscribe Full\" to receive full copies of new messages sent via email."
				to = users[str(user_id)]["Email"]
				message_plain = html2text.html2text(message_html)
				del users[str(user_id)]
				SendMessage(sender, to, subject, message_html, message_plain)

	logs["Last Enroll Message Index"] = last_max_msg_index
	logs["Last Enroll Run"] = str(datetime.datetime.now())

	with open(user_file, 'w+') as f:
		f.write(json.dumps(users))

	with open(log_file, 'w+') as f:
		f.write(json.dumps(logs))

	return cursor, logs, users

try:
	with open(log_file, 'r') as f:
		logs = json.load(f)
except:
	logs = {}
	logs["Last Full Run"] = str(datetime.datetime.now())
	logs["Last Simple Run"] = str(datetime.datetime.now() - datetime.timedelta(minutes = 31))
	logs["Last Enroll Run"] = str(datetime.datetime.now())
	logs["Last Full Message Index"] = 1000000
	logs["Last Simple Message Index"] = 1000000
	logs["Last Enroll Message Index"] = 1000000

try:
	with open(user_file, 'r') as f:
		users = json.load(f)
except:
	users = {}

while True:
	try:
		os.system('cls')

		start_time = datetime.datetime.now()

		print("Connecting to database.")
		cnxn = pyodbc.connect('Driver={SQL Server};' + 'Server={};Database={};Port={};UID={};PWD={}'.format(settings["Server"], settings["Database"], settings["Port"], settings["User"], settings["Password"]))
		cnxn.setencoding('utf-8')
		cursor = cnxn.cursor()

		cursor, logs, users = enroll_check(direct_ip, cursor, logs, user_file, users)
		print("Done.\n")

		simple_users = {}
		full_users = {}

		for x in users:
			if users[x]["Type"].lower() == "simple":
				simple_users[x] = users[x]
			elif users[x]["Type"].lower() == "full":
				full_users[x] = users[x]

		time_since_last_simple = datetime.datetime.now() - datetime.datetime.strptime(logs["Last Simple Run"], '%Y-%m-%d %H:%M:%S.%f')

		if time_since_last_simple.total_seconds() > 1800 and simple_users != {}: #30 minutes

			cursor, logs = simple_notifications(direct_ip, simple_users, cursor, logs)
			print ("Done.\n")

		if full_users != {}:
			cursor, logs = full_genius_messages(direct_ip, full_users, cursor, logs)

		cursor.close()
		del cursor
		cnxn.close()

		print("Connection closed.")

		print(str(datetime.datetime.now()) + " Done.")

		end_time = datetime.datetime.now()
		run_time = int(round((end_time - start_time).total_seconds()))
		if run_time < 300:
			delay = 300 - run_time
		else:
			delay = 60

		time.sleep(delay)
		
	except Exception as e:
		print(e)
		with open (error_file, 'a+') as f:
			f.write("Messages error: " + str(datetime.datetime.now()) + " " +str(e) + "\n\n")
		time.sleep(600)
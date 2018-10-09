# GeniusMessages
Forward genius messages to users email.

Settings file format:
{"Driver": pyodbc Driver, "Server": Server, "Database": Database_Name, "Port": Port, "User": Username, "Password": Password, "Direct IP": IP}

Users enroll by sending a Genius message to themselves with one of the following subject lines (not case sensitive):

"Email Subscribe Simple" - checks every 30 minutes for new messages for the user and sends a message notifying user of the number of new unread messages since the last run.

"Email Subscribe Full" - checks for new unread messages every 5 minutes and sends a full copy to the user's email.

"Email Unsubscribe" - removes user from all notification Emails

Users may only opt into full or simple notifications, not both. Sending a message as above with a different type will change the type the user will receive. The last message sent takes priority for subscriptions.

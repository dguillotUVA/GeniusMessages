import json
import os
import pyodbc

path = os.path.dirname(os.path.realpath(__file__))
settings_file = os.path.join(path, 'settings.txt')
user_file = os.path.join(path, 'users.txt')

with open(settings_file, 'r') as f:
    settings = json.load(f)


def get_user_info(settings, user_id):
    cnxn = pyodbc.connect('Driver={SQL Server};' + 'Server={};Database={};Port={};UID={};PWD={}'.format(settings["Server"], settings["Database"], settings["Port"], settings["User"], settings["Password"]))
    cnxn.setencoding('utf-8')
    cursor = cnxn.cursor()
    cursor.execute("SELECT USERINDEX, USERNAME, EMAIL FROM OPENQUERY([{}],'SELECT UserIndex, CONCAT(Users.FirstName, '' '', Users.LastName) AS Username, Email FROM Users WHERE UserIndex = {}')".format(settings["Direct IP"], user_id))
    user_info = cursor.fetchall()
    cursor.close()
    del cursor
    cnxn.close()
    return user_info[0]

quit = "no"

while quit != 'y':
    try:
        with open(user_file, 'r') as f:
            users = json.load(f)
    except:
        users = {}
    add_remove = input("Do you wish to add or remove a user from a list (a/r)? ").lower()

    if add_remove == "a":

        notify_type = input("Which list are you adding a user to (simple/full)? ").lower()

        if notify_type == "full" or notify_type == "simple":
            user_id = input("What is the User ID of the person you are adding? ")
            user_info = get_user_info(settings, user_id)
            print("You want to add {} whose email is {} to receive {} notifications.".format(user_info[1], user_info[2], notify_type))
            cont = input("Is this correct (y/n)? ").lower()

            if cont == "y":
                if user_id in users:
                    print("That user is already on the user list.")
                
                else:
                    users[str(user_id)] = {"Name": user_info[1], "Email": user_info[2], "Type": notify_type}

                    with open(user_file, 'w+') as f:
                        f.write(json.dumps(users))

                    print("The following was added to the user list:\nUser ID: {}\nName: {}\nEmail: {}\nType: {}\n".format(user_info[0], user_info[1], user_info[2], notify_type))

            elif cont == "n":
                print("The user was NOT added.")

            else:
                print("That is not a valid option.")

        else:
            print("That is not a valid option.")

    elif add_remove == "r":
        user_id = input("What is the User ID of the person you are removing? ")
        if user_id in users:
            user_name = users[user_id]["Name"]
            cont = input("You want to remove the user {}. Is this correct (y/n)? ".format(user_name)).lower()

            if cont == "y":             
                del users[str(user_id)]

                with open(user_file, 'w') as f:
                    f.write(json.dumps(users))
                            
                print("{} was removed from the notifications list.".format(user_name))

            elif cont == "n":
                print("{} was NOT removed from the notifications list.".format(user_name))

            else:
                print("That is not a valid option.") 

        else:
            print("That user is not on the messages list.")

    else:
        print("That was not a valid selection. Please try again.")

    quit = input("Do you want to quit (y/n)? ").lower()

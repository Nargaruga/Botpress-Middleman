from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater
from telegram.ext import MessageHandler, Filters
import requests
import os
import sys
import logging

#Botpress API URL
botpress_url = "http://localhost:3000/api/v1/bots/report-handling/converse/"

#Configure logging
logging.basicConfig(filename = "logging.log",
                    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level = logging.INFO)
logger = logging.getLogger("botpress_middleman")

#Configure the Updater, which allows us to receive messages from Telegram
try:
    with open("token.txt") as f:
        token = f.read().strip()
except IOError:
    logger.log(logging.CRITICAL, "Errore durante la lettura del file \"token.txt\".")
    sys.exit()

updater = Updater(token = token, use_context = "true")
dispatcher = updater.dispatcher

#Forward the user's message to Botpress and handles the response
def handle_message(update, context):
    result = forward(update, context)
    chat_id = update.effective_chat.id

    for response in result["responses"]:
        #type == custom means it's a choice
        if response["type"] == "custom":
            keyboard = []
            #quick_replies contains all of the choice's options,
            #   we create a keyboard button for each one of them.
            for reply in response["quick_replies"]:
                keyboard.append([KeyboardButton(reply["title"])])
    
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard = True)
            context.bot.send_message(chat_id = chat_id,
                                text = response["wrapped"]["text"],
                                reply_markup = reply_markup)

        #type == text means the message's contents are plain text
        if response["type"] == "text":
            #In this casse it contains the paths to the images we should send to the user...
            if "[$PATHS]" in response["text"]:
                paths = response["text"].replace("[$PATHS]", "").split("|")
                for i,path in enumerate(paths):
                    context.bot.send_photo(chat_id = chat_id,
                                        photo=open(path, 'rb'),
                                        caption=i+1)
                                        
                    #Delete the image from the filesystem
                    os.remove(path)
                    
            #...otherwise it's just a text message
            else:
                context.bot.send_message(chat_id = chat_id,
                                     text = response["text"])
            

#Composes the payload and sends the mssage to Botpress
def forward(update, context):
    text = update.message.text #None if the message isn't plain text
    photos = update.message.photo #None if the message isn't a photo
    location = update.message.location #None if the message isn't coordinates

    user_id = update.message.from_user.id #Id of the user who sent the message

    #Appropriately build the payload based on the user's message
    if(text):
        payload = {"type":"text", "text":"{0}".format(validate_input(update.message.text))}
    elif(photos):
        photo_id = photos[-1].file_id
        file = context.bot.get_file(photo_id)
        payload = {"type":"text", "text":"[$PHOTO]{0}".format(file["file_path"])}
    elif(location):
        payload = {"type":"text", "text":"[$COORDS]{0}|{1}".format(location["latitude"], location["longitude"])}
    else:
        payload = {"type":"text", "text":"[$UNSUPPORTED]"}

    #Finally send the message to Botpress and return the answer
    try:
        result = requests.post(botpress_url + str(user_id), payload).json() 
    except requests.exceptions.ConnectionError: 
        logger.log(logging.CRITICAL, "Connessione a Botpress fallita.")
        notifyUser(update.effective_chat.id, context)
    
    return result

#Removes special, reserved substrings from the user's message
def validate_input(message):
    return message.replace("[$PHOTO]", " ").replace("[$COORDS]", " ").replace("[$UNSUPPORTED]", " ").strip()

#Notifies the user that the system is unreachable
def notifyUser(chat_id, context):
    context.bot.send_message(chat_id = chat_id,
                        text = "Il servizio è al momento non disponibile. " +
                            "I nostri operatori cercheranno di risolvere " +
                            "il problema il prima possibile.")

forward_handler = MessageHandler(Filters.all, handle_message)
dispatcher.add_handler(forward_handler)

updater.start_polling()
updater.idle()
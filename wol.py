# coding=utf-8
import telebot
import json
import threading
import time
import signal
import sys
from wakeonlan import send_magic_packet
import icmplib
import requests
from datetime import datetime, timedelta

## Set VARIABLEs ##
path_json = "/home/pi/MinecraftServerJvJ/"
#path_json = "./"

env={}
try:
    with open(path_json+"env.json") as json_file:
        env = json.load(json_file)
except:
    print("Error - ENV: Cannot open critical environmental variable. Exiting...")
    sys.exit(1)

bot = telebot.TeleBot(env["token"], parse_mode="HTML")

password=env["password"]
interface_client=env["interface_client"]
mac_server=env["mac_server"]
ip_server=env["ip_server"]
port_server=env["port_server"]
secret_server=env["secret_server"]

users={} #dict of dictionaries to store state-variables for each user
status_server=False
maintenance=False
last_server_message=datetime.now()-timedelta(minutes=1)
last_on_factorio_message=datetime.now()-timedelta(minutes=1)
last_on_minecraft_message=datetime.now()-timedelta(minutes=1)

## FIRST STEPs ##

try:
    with open(path_json+"users.json") as json_file:
        users = json.load(json_file)
    sup=list(users.keys())
    for el in sup:
        users[int(el)]=users[el]
        users.pop(el)
except:
    print("Info - USERS: No data available or wrong format. First initialization.")

## HANDLERs ##

@bot.message_handler(commands=['start'])
def start(message):
    global users
    if message.from_user.username is None:
        bot.send_message(message.chat.id, "Non possiedi uno username.\nInserisci uno username dalle impostazioni di telegram per poter utilizzare questo servizio")
    elif message.from_user.id in users and users[message.from_user.id]["isRegistered"]:
        bot.send_message(message.chat.id, "\U0001F917 Bentornato " + message.from_user.first_name +"!")
    elif message.from_user.id not in users:
        bot.send_message(message.chat.id, "\U0001F510 Per registrarti nel sistema inserisci la password...")
        users[message.from_user.id]={}
        users[message.from_user.id]["username"]=message.from_user.username
        users[message.from_user.id]["isRegistered"]=False
        users[message.from_user.id]["isAdmin"]=False
        users[message.from_user.id]["notify"]=True
        users[message.from_user.id]["attempt"]=3
        users[message.from_user.id]["waitForPass"]=True
        save_users()
    elif users[message.from_user.id]["attempt"]>0:
        bot.send_message(message.chat.id, "\U0001F510 Inserisci la password per entrare nel sistema...")
    else:
        bot.send_message(message.chat.id, "\U00002B55 Ci spiace " + message.from_user.first_name +", risulti bannato dal sistema")

@bot.message_handler(commands=['ban'])
def ban(message):
    global users
    if check_admin(message.from_user):
        txt=message.text.split()
        if len(txt)==2 and txt[1].isnumeric() and int(txt[1]) in users and not users[int(txt[1])]["isAdmin"]:
            user=int(txt[1])
            users[user]["isRegistered"]=False
            users[user]["attempt"]=0
            save_users()
            bot.send_message(message.chat.id, "\U00002705 L'utente "+str(user)+" è stato bannato dal sistema")
        else:
            bot.send_message(message.chat.id, "Uso incorretto oppure utente inesistente o admin. Usa invece:\n<code>/ban [user_id]</code>")

@bot.message_handler(commands=['reset'])
def reset(message):
    global users
    if check_admin(message.from_user):
        txt=message.text.split()
        if len(txt)==2 and txt[1].isnumeric() and int(txt[1]) in users and not users[int(txt[1])]["isAdmin"]:
            user=int(txt[1])
            del users[user]
            save_users()
            bot.send_message(message.chat.id, "\U00002705 L'utente "+str(user)+" è stato resettato e può ora registrarsi")
        else:
            bot.send_message(message.chat.id, "Uso incorretto o utente inesistente. Usa invece:\n<code>/reset [user_id]</code>")

@bot.message_handler(commands=['say'])
def say(message):
    global users
    if check_admin(message.from_user):
        if len(message.text.split())>=2:
            notify_except('', "AVVISO SERVER\n" + message.text[4:].strip())

@bot.message_handler(commands=['listusers'])
def listusers(message):
    global users
    if check_admin(message.from_user):
        txt=""
        for user in users:
            if users[user]["isRegistered"]:
                txt+="\U0001F7E2 "
            elif users[user]["attempt"]==0:
                txt+="\U0001F534 "
            else:
                txt+="\U0001F7E1 "
            txt+="<code>"+str(user)+"</code> - "+users[user]["username"]
            if users[user]["isAdmin"]:
                txt+=" <b>ADMIN</b>"
            txt+="\n"
        bot.send_message(message.chat.id, txt)

@bot.message_handler(commands=['maintenance'])
def listusers(message):
    global users, maintenance
    if check_admin(message.from_user):
        txt=message.text.split()
        if len(txt)==2 and (txt[1].upper()=="ON" or txt[1].upper()=="OFF"):
            maintenance = True if txt[1].upper()=="ON" else False
            bot.send_message(message.chat.id, "Manutenzione "+("ATTIVATA" if maintenance else "DISATTIVATA"))
        else:
            bot.send_message(message.chat.id, "La manutenzione risulta "+("ATTIVA" if maintenance else "NON ATTIVA"))

@bot.message_handler(commands=['notify_on'])
def listusers(message):
    global users
    if check_auth(message.from_user):
        users[message.from_user.id]["notify"]=True
        save_users()
        bot.send_message(message.chat.id, "Impostato")

@bot.message_handler(commands=['notify_off'])
def listusers(message):
    global users
    if check_auth(message.from_user):
        users[message.from_user.id]["notify"]=False
        save_users()
        bot.send_message(message.chat.id, "Impostato")


@bot.message_handler(commands=['on_server'])
def on(message):
    global status_server, last_server_message
    if check_auth(message.from_user):
        if not status_server and datetime.now()>=last_server_message+timedelta(seconds=29):
            bot.send_message(message.chat.id, "Avvio server in 30 secondi...")
            last_server_message=datetime.now()
            for i in range(5):
                send_magic_packet(mac_server, ip_address='255.255.255.255', interface=interface_client)
                time.sleep(.1)
            notify_except(message.from_user.id, "Il server è stato avviato da "+message.from_user.first_name + "\n\U0000231B Attendere 30 secondi...")
        elif status_server:
            bot.send_message(message.chat.id, "Il server risulta già avviato")
        else:
            bot.send_message(message.chat.id, "E' già stato inviato un comando simile... Attendere almeno altri "+ str((last_server_message+timedelta(seconds=30)-datetime.now()).seconds) +" secondi")

@bot.message_handler(commands=['off_server'])
def off(message):
    global status_server, last_server_message
    if check_auth(message.from_user):
        if status_server and datetime.now()>=last_server_message+timedelta(seconds=29):
            bot.send_message(message.chat.id, "Spengo server in 30 secondi...")
            last_server_message=datetime.now()
            send_command("shutdown")
            notify_except(message.from_user.id, "Il server è stato spento da "+message.from_user.first_name)
        elif not status_server:
            bot.send_message(message.chat.id, "Il server risulta già spento")
        else:
            bot.send_message(message.chat.id, "E' già stato inviato un comando simile... Attendere almeno altri "+ str((last_server_message+timedelta(seconds=30)-datetime.now()).seconds) +" secondi")

@bot.message_handler(commands=['on_factorio'])
def on_factorio(message):
    global last_on_factorio_message
    if check_auth(message.from_user):
        if status_server and datetime.now()>=last_on_factorio_message+timedelta(seconds=29):
            r = send_command("startFactorio")
            if r.status_code==200:
                bot.send_message(message.chat.id, "Avvio Factorio in massimo 30 secondi...")
                last_on_factorio_message=datetime.now()
            else:
                bot.send_message(message.chat.id, "Errore del server:\n'<b>("+str(r.status_code)+")</b> "+r.text+"'")
        elif not status_server:
            bot.send_message(message.chat.id, "Il server risulta spento")
        else:
            bot.send_message(message.chat.id, "E' già stato inviato un comando simile... Attendere almeno altri "+ str((last_on_factorio_message+timedelta(seconds=30)-datetime.now()).seconds) +" secondi")

@bot.message_handler(commands=['off_factorio'])
def off_factorio(message):
    global last_on_factorio_message
    if check_auth(message.from_user):
        if status_server:
            r = send_command("stopFactorio")
            if r.status_code==200:
                bot.send_message(message.chat.id, "Spengo Factorio")
            else:
                bot.send_message(message.chat.id, "Errore del server:\n'<b>("+str(r.status_code)+")</b> "+r.text+"'")
        else:
            bot.send_message(message.chat.id, "Il server risulta spento")

@bot.message_handler(commands=['on_minecraft'])
def on_minecraft(message):
    global last_on_minecraft_message
    if check_auth(message.from_user):
        if status_server and datetime.now()>=last_on_minecraft_message+timedelta(seconds=59):
            r = send_command("startMinecraft")
            if r.status_code==200:
                bot.send_message(message.chat.id, "Avvio Minecraft in massimo 60 secondi...")
                last_on_minecraft_message=datetime.now()
            else:
                bot.send_message(message.chat.id, "Errore del server:\n'<b>("+str(r.status_code)+")</b> "+r.text+"'")
        elif not status_server:
            bot.send_message(message.chat.id, "Il server risulta spento")
        else:
            bot.send_message(message.chat.id, "E' già stato inviato un comando simile... Attendere almeno altri "+ str((last_on_minecraft_message+timedelta(seconds=60)-datetime.now()).seconds) +" secondi")

@bot.message_handler(commands=['off_minecraft'])
def off_minecraft(message):
    global last_on_minecraft_message
    if check_auth(message.from_user):
        if status_server:
            r = send_command("stopMinecraft")
            if r.status_code==200:
                bot.send_message(message.chat.id, "Spengo Minecraft")
            else:
                bot.send_message(message.chat.id, "Errore del server:\n'<b>("+str(r.status_code)+")</b> "+r.text+"'")
        else:
            bot.send_message(message.chat.id, "Il server risulta spento")

@bot.message_handler(commands=['status'])
def status(message):
    if check_auth(message.from_user):
        server, minecraft, factorio = check_server()
        txt=""
        if not server:
            txt = "Server:          \U0001F534 OFF"
        else:
            txt = "Server:          \U0001F7E2 ON"
            if minecraft:
                txt += "\n |--> Minecraft: \U0001F7E2 ON"
            else:
                txt += "\n |--> Minecraft: \U0001F534 OFF"
            if factorio:
                txt += "\n |--> Factorio:  \U0001F7E2 ON"
            else:
                txt += "\n |--> Factorio:  \U0001F534 OFF"
        bot.send_message(message.chat.id, "<code>"+txt+"</code>\n\n Le notifiche sono "+("ACCESE" if users[message.from_user.id]["notify"] else "SPENTE"))

@bot.message_handler(commands=['help'])
def help(message):
    txt = "L'infrastuttura è composta da un server fisico che contiene due server virtuali con Minecraft e Factorio e un middleware che li gestisce. Assicurarsi dunque sia acceso il server fisico prima di accendere quelli virtuali. I comandi disponibili sono:\n"
    txt+= "/on_server - Avvia il server (circa 30 secondi per avviarsi)\n"
    txt+= "/off_server - Ferma il server\n"
    txt+= "/on_factorio - Avvia il server Factorio (circa 30 secondi per avviarsi)\n"
    txt+= "/off_factorio - Ferma il server Factorio\n"
    txt+= "/on_minecraft - Avvia il server Minecraft (circa 60 secondi per avviarsi)\n"
    txt+= "/off_minecraft - Ferma il server Minecraft\n"
    txt+= "/status - Visualizza lo stato dei server\n"
    txt+= "/help - Visualizza questa guida\n"
    txt+= "/notify_on - Abilita le notifiche per il tuo account\n"
    txt+= "/notify_off - Disabilita le notifiche per il tuo account"
    bot.send_message(message.chat.id, txt)

## GENERAL HANDLER ##
from itertools import groupby

@bot.message_handler(content_types=['text'])
def text(message):
    global users
    if message.from_user.id in users and users[message.from_user.id]["waitForPass"]:
        if users[message.from_user.id]["attempt"]>0 and message.text==password:
            users[message.from_user.id]["isRegistered"]=True
            users[message.from_user.id]["waitForPass"]=False
            save_users()
            bot.send_message(message.chat.id, "\U0001F7E2 Password corretta! Ciao "+message.from_user.first_name+", benvenuto nel sistema \U0001F44B")
            notify_admins("\U00002705 L'utente "+message.from_user.username+" con id <code>"+str(message.from_user.id)+"</code> è stato registrato nel sistema")
        elif users[message.from_user.id]["attempt"]>0:
            users[message.from_user.id]["attempt"]-=1
            save_users()
            if users[message.from_user.id]["attempt"]>0:
                bot.send_message(message.chat.id, "\U0001F534 Password errata! Hai a disposizione ancora "+str(users[message.from_user.id]["attempt"])+" tentativo/i")
            else:
                bot.send_message(message.chat.id, "\U0001F534 Password errata! Hai a esaurito i tentativi a tua disposizione! Contatta un admin...")
                notify_admins("\U0000274E L'utente "+message.from_user.username+" con id <code>"+str(message.from_user.id)+"</code> ha inserito erroneamente la password per 3 volte")


## SUPPORT FUNCTIONs ##

def save_users():
    global users
    with open(path_json+"users.json", "w") as outfile:
        json.dump(users, outfile)


def notify_admins(text):
    global users
    for user in users:
        if users[user]["isRegistered"] and users[user]["isAdmin"]:
            try:
                bot.send_message(user,text)
            except:
                pass

def notify_except(exception, text):
    global users, maintenance
    if not maintenance:
        text="\U00002139 "+text
        for user in users:
            if users[user]["isRegistered"] and users[user]["notify"] and user!=exception:
                try:
                    bot.send_message(user,text)
                except:
                    pass

def check_auth(user):
    global users
    if user.id in users and users[user.id]["isRegistered"]:
        if users[user.id]["username"]!=user.username:
            users[user.id]["username"]=user.username
            save_users()
        return True
    else:
        bot.send_message(user.id,"\U00002B55 Ci spiace " + user.first_name +", non risulti registrato nel sistema")
        return False

def check_admin(user):
    global users
    if user.id in users and users[user.id]["isRegistered"] and users[user.id]["isAdmin"]:
        if users[user.id]["username"]!=user.username:
            users[user.id]["username"]=user.username
            save_users()
        return True
    else:
        bot.send_message(user.id,"\U00002B55 Ci spiace " + user.first_name +", non risulti registrato o admin nel sistema")
        return False

def send_command(cmd):
    r = requests.get("http://"+ip_server+":"+port_server+"/"+cmd+"?"+secret_server)
    return r

def check_server():
    minecraft = False
    factorio = False
    if status_server:
        r = requests.get("http://"+ip_server+":"+port_server+"/checkMinecraft?"+secret_server)
        minecraft = r.text=="true"
        r = requests.get("http://"+ip_server+":"+port_server+"/checkFactorio?"+secret_server)
        factorio = r.text=="true"
    return status_server, minecraft, factorio



## POLLING ##

def thread_function():
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5, logger_level=0)
        except:
            print("ERROR - PROGRAM: waiting for network...")
            time.sleep(2)

th_poll = threading.Thread(target=thread_function)
th_poll.daemon = True
th_poll.start()

## MAIN PROGRAM (handles the actuator)##

def exit(signum, frame):
    print("Info - Exiting...")
    notify_admins("\U0000274E Bot interrotto")
    sys.exit()

signal.signal(signal.SIGINT, exit)
signal.signal(signal.SIGTERM, exit)

proceed = False
while not proceed:
    try:
        notify_admins("\U00002705 Bot avviato")
        proceed = True
    except:
        print("ERROR - PROGRAM: waiting for network...")
        time.sleep(2)

while True:
    res = icmplib.ping(ip_server, count=4, timeout=4, interval=0.25)
    ping_response = res.is_alive
    if ping_response != status_server:
        status_server = ping_response
        notify_except('', "Server ON \U0001F7E2" if status_server else "Server OFF \U0001F534")
    time.sleep(10)
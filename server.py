from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread
from binascii import crc32
from termcolor import colored, COLORS
from argon2 import PasswordHasher
import os

def accept_connections():
  while True:
    client, addr = SERVER.accept()
    print(f'Incoming connection from {addr}')
    Thread(target=single_client, args=(client,addr)).start()

def single_client(client,addr):
  ip_parts = addr[0].split('.')
  username = str(hex(crc32((ip_parts[0]+ip_parts[3]).encode('utf8'))))+'#'+str(addr[1])
  clients[client] = username
  nc[client] = 'white'
  welcome_msg = f'Welcome {username}\nOnline: {get_clients()[0]}\nType /help for help.'
  client.send(welcome_msg.encode())
  join_msg = f'{username} has joined the room.'
  broadcast_msg(join_msg.encode())
  try:
    while True:
      msg = client.recv(BUFFERSIZE)
      utf8 = msg.decode('utf8')
      if utf8.startswith('/'):
        handle_commands(client, utf8)
      else:
        broadcast_msg(msg, colored(clients[client], nc[client]) + ': ')
  except OSError:
    pass

def handle_commands(client, msg):
  parts = msg[1:].split()
  if len(parts) < 1: return
  if parts[0] == 'leave':
    disconnect(client)
  elif parts[0] == 'nick':
    if len(parts) < 2: return
    new_name = parts[1]
    password = None
    if len(parts) > 2: password = parts[2]
    if validate_name(new_name, password=password):
      isgenuine = ""
      if password is not None: isgenuine = " (authenticated)"
      broadcast_msg(f'{clients[client]} is now {new_name}{isgenuine}'.encode())
      clients[client] = new_name
    else:
      client.send('Wrong password!'.encode())
  elif parts[0] == 'register':
    if len(parts) < 2: return
    password = parts[1]
    if validate_name(clients[client]):
      if register(clients[client], password):
        client.send(f'Successfully registered {clients[client]}'.encode())
      else:
        client.send(f'Unable to register'.encode())
  elif parts[0] == 'nc':
    if len(parts) < 2: return
    color = parts[1]
    if color in COLORS: nc[client] = parts[1]
    else:
      client.send(f"Available colors: {', '.join(COLORS)}".encode())
  elif parts[0] == '/help':
   help_msg = [
     "/leave - Leave the server",
     "/nick <name> (password) - Change your nickname. Password is only required if the account is registered.",
     "/register <password> - Register your current username.",
     "/nc - Change your nickname color"
   ]
   for i in help_msg:
     client.send(i.encode())

def disconnect(client):
  print(f'{clients[client]} has disconnected')
  client.close()
  client_leaving = clients[client]
  del clients[client]
  broadcast_msg(f'{client_leaving} has disconnected'.encode())

def broadcast_msg(msg, name=""):
  for client in clients:
    try:
      client.send(name.encode() + msg)
    except BrokenPipeError:
      pass

def get_clients():
  real_clients_num = 0
  real_clients_name = []
  for k, v in clients.items():
    real_clients_num += 1
    real_clients_name.append(v)
  return real_clients_num, real_clients_name

def validate_name(name, register=False, password=None):
  file = ACCS_DIR+'/'+name
  if not os.path.exists(file):
    return True
  elif password is not None:
    with open(file, 'r') as f:
      exp = f.read()
      f.close()
      if ph.verify(exp, password):
        return True
      else:
        return False
  else:
    return False

def register(name, password):
  file = ACCS_DIR+'/'+name
  if os.path.exists(file):
    return False
  with open(file, 'w') as f:
    hash = ph.hash(password)
    f.write(hash)
    f.close()
  return True

if __name__ == "__main__":
  clients = {}
  nc = {}
  ph = PasswordHasher()
  ACCS_DIR = 'accounts'
  HOST = '0.0.0.0'
  PORT = 6060
  BUFFERSIZE = 1024
  ADDR = (HOST, PORT)
  SERVER = socket(AF_INET, SOCK_STREAM)
  SERVER.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
  SERVER.bind(ADDR)
  SERVER.listen(2)
  print("Ready ✓")
  ACCEPT_THREAD = Thread(target=accept_connections)
  ACCEPT_THREAD.start()
  ACCEPT_THREAD.join()
  SERVER.close()

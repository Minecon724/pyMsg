from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread
from binascii import crc32
from termcolor import colored, COLORS
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from string import ascii_letters, digits
import os, yaml, sys, traceback

def load_config():
  if not os.path.exists('config.yml'):
    print("config.yml doesn't exist :(")
    print("Make sure you have cloned the repository from github")
    sys.exit(1)
  f = open('config.yml', 'r')
  cfg = yaml.safe_load(f)
  f.close()
  return cfg

def accept_connections():
  while True:
    client, addr = SERVER.accept()
    print(f'Incoming connection from {addr[0]}:{addr[1]}')
    Thread(target=single_client, args=(client,addr)).start()

def single_client(client,addr):
  ip_parts = addr[0].split('.')
  username = str(hex(crc32((ip_parts[0]+ip_parts[3]).encode('utf8'))))+'#'+str(addr[1])
  clients[client] = username
  rooms[client] = default_room
  nc[client] = config['misc']['default_name_color']
  welcome_msg = '\n'.join(config['misc']['motd']).replace('%u', username).replace('%o', str(get_clients()[0]))
  client.send(welcome_msg.encode())
  join_msg = f'{username} has joined the room.'
  broadcast_in_room(rooms[client], join_msg.encode())
  max_msg_size = config['security']['max_msg_size']
  while True:
    try:
      msg = client.recv(BUFFERSIZE)
      utf8 = msg.decode('utf8')
      if len(utf8) > max_msg_size:
        client.send(f'(!) Maximum message length is {max_msg_size}'.encode())
        continue
      if utf8.startswith('/'):
        handle_commands(client, utf8)
      elif utf8.startswith('!'):
        broadcast_msg(msg, f'({rooms[client]}) ' + colored(clients[client], nc[client]) + ': ')
      else:
        broadcast_in_room(rooms[client], msg, colored(clients[client], nc[client]) + ': ')
    except OSError:
      disconnect(socket)
    except Exception:
      print(traceback.format_exc())
      pass

def handle_commands(client, msg):
  parts = msg[1:].split()
  if len(parts) < 1: return
  if parts[0] in cmds['leave']:
    disconnect(client)
  elif parts[0] in cmds['nick']:
    if len(parts) < 2:
      client.send("(!) I can't change your name to nothing!")
      return
    new_name = parts[1]
    if not all(c in allowed_name for c in new_name):
      client.send(f"(!) Usernames cannot contain characters other than: {''.join(allowed_name)}".encode())
      return
    elif new_name in list(clients.values()):
      client.send(f'(!) This username is taken'.encode())
      return
    password = None
    if len(parts) > 2: password = parts[2]
    is_valid = validate_name(new_name, password=password)
    if is_valid:
      broadcast_msg(f'({rooms[client]}) {clients[client]} is now {new_name}'.encode())
      clients[client] = new_name
    else:
      if password is None:
        client.send('(!) A password is required!'.encode())
      else:
        client.send('(!) Wrong password!'.encode())
  elif parts[0] in cmds['register']:
    if len(parts) < 2:
      client.send("(!) You don't need to register if you don't want to have a password!")
      return
    password = parts[1]
    if validate_name(clients[client]):
      if register(clients[client], password):
        client.send(f'Successfully registered {clients[client]}'.encode())
      else:
        client.send(f'Password changed successfully'.encode())
  elif parts[0] in cmds['nc']:
    if len(parts) > 1 and parts[1] in COLORS: nc[client] = parts[1]
    else:
      client.send(f"Available colors: {', '.join(COLORS)}".encode())
  elif parts[0] in cmds['help']:
    help_msg = config['misc']['help']
    client.send('\n'.join(help_msg).encode())
  elif parts[0] in cmds['room']:
    if len(parts) < 2:
      client.send("(!) Where do you want to go?".encode())
      return
    switch_room(client, parts[1])
  else:
    client.send('(!) Unknown command.'.encode())

def disconnect(client):
  print(f'{clients[client]} has disconnected')
  client.close()
  client_leaving = clients[client]
  room_leaving = rooms[client]
  del clients[client]
  del rooms[client]
  broadcast_in_room(room_leaving, f'{client_leaving} has disconnected'.encode())

def broadcast_msg(msg, name=""):
  for client in clients:
    client.send(name.encode() + msg)

def broadcast_in_room(room, msg, name=""):
  for client in clients:
    if rooms[client] == room:
      client.send(name.encode() + msg)

def get_clients():
  real_clients_num = 0
  real_clients_name = []
  for k, v in clients.items():
    real_clients_num += 1
    real_clients_name.append(v)
  return real_clients_num, real_clients_name

def validate_name(name, password=None):
  file = ACCS_DIR+'/'+name
  if not os.path.exists(file):
    return True
  elif password is not None:
    f = open(file, 'r')
    exp = f.read()
    f.close()
    try:
      is_valid = ph.verify(exp, password)
    except VerifyMismatchError:
      is_valid = False
    if is_valid:
      if ph.check_needs_rehash(exp):
        change_password(name, password)
      return True
    else:
      return False
  else:
    return False

def save_hashed(file, password):
  f = open(file, 'w')
  hash = ph.hash(password)
  f.write(hash)
  f.close()

def register(name, password):
  file = ACCS_DIR+'/'+name
  if not os.path.exists(file):
    save_hashed(file, password)
    return True
  return False

def switch_room(client, room):
  broadcast_in_room(rooms[client], f'{clients[client]} has left the room'.encode())
  rooms[client] = room
  broadcast_in_room(room, f'{clients[client]} has joined the room'.encode())

def change_password(name, password):
  file = ACCS_DIR+'/'+name
  save_hashed(file, password)

def load_commands_and_aliases(cfg):
  cmds = {}
  for k, v in cfg.items():
    cmds[k] = []
    if v['enable'] is True or k == 'leave':
      cmds[k].append(k)
      cmds[k].extend(v['aliases'])
  return cmds
  

if __name__ == "__main__":
  print('Starting server...')
  config = load_config()
  cmds = load_commands_and_aliases(config['commands'])
  clients = {}
  rooms = {}
  nc = {}
  ph = PasswordHasher()
  allowed_name = ascii_letters + digits + '_'
  default_room = config['misc']['default_room']
  ACCS_DIR = config['misc']['save_accs_in']
  HOST = config['net']['host']
  PORT = config['net']['port']
  BUFFERSIZE = 4096
  ADDR = (HOST, PORT)
  SERVER = socket(AF_INET, SOCK_STREAM)
  SERVER.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
  SERVER.bind(ADDR)
  SERVER.listen(2)
  print(f'Server running on {HOST}:{PORT}')
  ACCEPT_THREAD = Thread(target=accept_connections)
  ACCEPT_THREAD.start()
  ACCEPT_THREAD.join()
  SERVER.close()

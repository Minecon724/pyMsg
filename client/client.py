from socket import socket, SOCK_STREAM, AF_INET
from threading import Thread
from signal import signal, SIGINT
from inquirer import prompt, Text
from colorama import init, Fore, Back, Style
import sys, os, traceback

def receive_msg():
  while True:
    try:
      msg = client_socket.recv(BUFFERSIZE).decode('utf8')
      if msg.startswith('(!)'):
        msg = Back.RED + msg + Style.RESET_ALL
      elif msg.startswith('(i)'):
        msg = Fore.MAGENTA + msg + Style.RESET_ALL
      print(msg)
    except Exception:
      print(traceback.format_exc())
      client_socket.close()
      sys.exit(1)

def send_msg():
  while True:
    try:
      msg = input()
      if not msg.startswith('/'):
        sys.stdout.write("\033[1A[\033[2K")
      if msg != '/leave':
        client_socket.send(msg.encode('utf8'))
      else:
        clean_exit()
    except EOFError:
      clean_exit()

def clean_exit():
  client_socket.send('/leave'.encode('utf8'))
  client_socket.close()
  sys.exit(0)

def handler(signal_recv, frame):
  clean_exit()

def get_data():
  questions = [
    Text('addr', message=f'Server address ({default_host})'),
    Text('port', message=f'Server port ({default_port})')
  ]
  answers = prompt(questions)
  if answers['addr'] == '':
    answers['addr'] = default_host
  if answers['port'] == '':
    answers['port'] = default_port
  data = (answers['addr'], int(answers['port']))
  return data

if __name__ == '__main__':
  default_host = 'localhost'
  default_port = '3456'
  init()
  HOST, PORT = get_data()
  print('Connecting...')
  signal(SIGINT, handler)
  BUFFERSIZE = 4096
  ADDR = (HOST, PORT)
  client_socket = socket(AF_INET, SOCK_STREAM)
  client_socket.connect(ADDR)
  print('-------------')
  receive_thread = Thread(target=receive_msg)
  receive_thread.start()
  send_msg()

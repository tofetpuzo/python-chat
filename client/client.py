import json
import os
import socket
import threading
import time

import constants
import protocol
from protocol import parse_json

from .command_utils import (AUTH_COMMANDS, MSG_COMMANDS, parse_auth,
                            parse_command)
from .screen_helpers import gather_input, refresh_all, setup_screen, quit_screen

has_quited = False

def start_client():
    global has_quited
    screen = setup_screen()
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((constants.IP, constants.PORT))
    except ConnectionRefusedError:
        print(
            "Could not connect :(."
            "\nFirst start Server with 'python main.py --server'"
        )
        return

    raw_msg = client_socket.recv(constants.MAX_MSG_LEN)
    payload = parse_json(raw_msg)
    if payload["status"] == 200:
        screen["out"]["printer"](
            "Connected to server!\n"
            + f"Server:{client_socket.getpeername()}\n"
            + f"Server:{client_socket.getsockname()}"
        )
    username = authenticate(client_socket, screen)
    if username:
        main_loop(client_socket, username, screen)


def authenticate(sock, screen):
    screen["out"]["printer"]("Possible commands: /login or /signup, term")
    auth_status = False

    while not auth_status:
        raw_command = gather_input(screen["in"])
        refresh_all(screen)
        try:
            command = parse_auth(raw_command)
        except AssertionError as e:
            screen["out"]["printer"](e)
            continue
        screen["out"]["printer"](command)

        if command["command"] == "/exit":
            screen["out"]["printer"](f"EXIT")
            quit_screen()
            return None

        send_message(sock, command)
        raw_msg = sock.recv(constants.MAX_MSG_LEN)
        response = parse_json(raw_msg)

        if response["status"] != protocol.AUTH_SUCCESS:
            error_code = response["status"]
            error_msg = response["message"]
            screen["out"]["printer"](f"Error {error_code}: {error_msg}")
            continue
                
        username = response["payload"]["username"]
        if command["command"] == "/signup":
            screen["out"]["printer"](
                f"Successfully created user {username}"
                + "Login with /login <username> <password>"
            )

        elif command["command"] == "/login":
            screen["out"]["printer"](f"Welcome {username}!")
            return username
        



def handle_recieved_message(response, printer):
    payload = response["payload"]
    if not response or not payload or payload["by"] == "user":
        printer(f"IGNORING REQUEST {payload}")
        return

    status = response["status"]
    if status == protocol.SEND_MESSAGE:
        printer(f"{payload['username']}: {payload['message']}")
    elif status in protocol.SUCCESS_CODES:
        pass
        #printer(f"Response: {response}")
    elif status in protocol.ERROR_CODES:
        printer(f"Error: {response}")
    else:
        raise ValueError(f"Invalid response code {status}")


def listen_server(sock, printer):
    global has_quited
    while not has_quited:
        raw_message = sock.recv(constants.MAX_MSG_LEN)
        try:
            decoded_message = protocol.parse_json(raw_message)
            handle_recieved_message(decoded_message, printer)
        except json.decoder.JSONDecodeError:
            printer('Server is offline... Shutting down application')
            time.sleep(1)


def send_message(sock, command):
    sock.send(protocol.encode(command))

def wait_user_input(sock, screen, out_printer):
    global has_quited
    while True:
        raw_command = gather_input(screen)
        try:
            command = parse_command(raw_command)
            if command["command"] == "/exit":
                break
            send_message(sock, command)
        except AssertionError as e:
                out_printer(e)
    has_quited = True
    quit_screen()
    os._exit(0)
        

def main_loop(sock, username, screen):
    global has_quited
    has_quited = False
    listen_thread = threading.Thread(
        target=listen_server, args=(sock, screen["out"]["printer"])
    )
    input_thread = threading.Thread(
        target=wait_user_input, args=(sock, screen["in"], screen["out"]["printer"])
    )

    listen_thread.start()
    input_thread.start()

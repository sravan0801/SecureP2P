# Socket module
import socket

# Module to make socket/file reads non blocking
import select

# os and sys utils
import sys
import os

# Module to perfom multi Processing
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection

# Module to de/serialze messages
import json

# Terminal utils
from termios import tcflush, TCIOFLUSH

# Available options for client
COMMANDS = {
    "get": "Get a list of connected users.",
    "connect <username>": "Connect to a specific user.",
    "END": "End server session.",
    "EOM": "End messaging session.",
}


def print_help_message():
    """
    Utility functions that print the commands available
    """
    print("\nAvailable Commands: ")
    for command, desc in COMMANDS.items():
        print(f"\t{command}: {desc}")
    print("\n")


# TODO:
# 1. Print username instead of the IP when exchanging messages
# 2. Message exchange btw the same client does not work
def p2p_message_exchange_handler(peer_socket: socket.socket) -> None:
    """
    Handle two client message exchange

    Parameters:
        peer_socket (socket.socket): socket that is connected to other client

    Returns:
        None
    """
    print(f"\nConnected to User{peer_socket.getpeername()}")
    print("send> ", end="", flush=True)

    while True:
        # Wait till any file/socket is ready to read
        rlist = select.select([sys.stdin, peer_socket], [], [])[0]
        if rlist == []:
            continue

        # If the ready file is stdin, get input from terminal and sent to other client
        # If soccket is ready for read, read socket and print it in output
        if sys.stdin in rlist:
            send_msg = input("send> ")
            if send_msg == "EOM":
                peer_socket.send(send_msg.encode())
                break
            peer_socket.send(send_msg.encode())
        if peer_socket in rlist:
            recv_msg = peer_socket.recv(1024).decode()
            if recv_msg == "EOM" or recv_msg == "":
                print("\r\nUser closed connection\n")
                break
            print(f"\rrecv> {recv_msg}\nsend> ", end="")


def p2p_connection_handler(
    p2p_connection_listen: socket.socket, stdin_fileno: int, message_queue: Connection
) -> None:
    """
    Handle incomming connection requests from other client

    Parameter:
        p2p_connection_listen (socket.socket): socket that is listening for incomming connection requests
        stdin_fileno (int): sys.stdin file no. This is required since this function will run in a separate Process
        message_queue (Connection): Process that runs the server_connection_handler() function can send messages to this process. Used to pause the message exchange with server when clients are communicating.

    Returns:
        None
    """
    sys.stdin = os.fdopen(stdin_fileno)

    while True:
        peer_socket, _ = p2p_connection_listen.accept()

        message_queue.send("0")

        # Flush the input that was queued
        tcflush(sys.stdin, TCIOFLUSH)

        # Check if user wants to connect
        opt = (
            input(
                f"\rUser {peer_socket.getsockname()} wants to connect. Accept connection?(Y/n): "
            )
            .strip()
            .lower()
        )

        # If no, close the connection
        if opt == "y" or opt == "":
            peer_socket.send("ACCEPTED".encode())
            p2p_message_exchange_handler(peer_socket)
        else:
            peer_socket.send("REFUSED".encode())

        # close peer socket
        peer_socket.close()

        # Resume the server_connection_handler process
        print("\rEnter Options: ", end="", flush=True)
        message_queue.send("1")

        tcflush(sys.stdin, TCIOFLUSH)


def server_connection_handler(
    clientSocket: socket.socket, stdin_fileno: int, message_queue: Connection
) -> None:
    """
    Handle message exchange between server and client

    Parameters:
        clientSocket (socket.socket): socket that is connected to the server
        stdin_fileno (int): sys.stdin file no. This is required since this function will run in a separate Process
        message_queue (Connection): Process that runs the p2p_connection_handler() function can send messages to this process. Used to pause the message exchange with server when clients are communicating.

    Returns:
        None
    """

    # Dictionary that maintains current active users
    active_users = dict()
    sys.stdin = os.fdopen(stdin_fileno)

    print_help_message()
    while True:
        print("\rEnter Options: ", end="")
        # Check if data is available, if the p2p_connection_handler is active stop this thread
        rlist = select.select([sys.stdin, message_queue], [], [])[0]
        if message_queue in rlist:
            message_queue.recv()
            message_queue.recv()
            continue

        client_message = input().strip()

        # Client exit
        if client_message.strip().lower() == "end":
            break

        # Get current active users from the server
        if client_message == "get":
            clientSocket.send(client_message.encode())
            active_users = json.loads(clientSocket.recv(1024).decode())
            print(f"\nConnected users: {active_users}\n")
        # Send a connection request to the client
        elif client_message.startswith("connect "):
            username = client_message.split(" ")[1]
            try:
                (target_ip, target_port) = active_users[username]
                peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                peer_socket.connect((target_ip, int(target_port)))

                print(f"Connecting to user{peer_socket.getpeername()}")
                if peer_socket.recv(1024).decode() == "REFUSED":
                    print("User declined connection request")
                    continue
                p2p_message_exchange_handler(peer_socket)

            except (ConnectionRefusedError, KeyError):
                print(
                    '\nInvalid username. Use "get" command for the updated list of active users\n'
                )
        else:
            print("Invalid Command")
            print_help_message()


def runClient() -> None:
    """
    Run the client logic
    """
    # Create a TCP socket and connect to server
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect(("", 11000))
    print("Connected to Server")

    # Create a P2P socket for other clients to connect
    p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    p2p_socket.listen()
    print(f"P2P socket listening on port {p2p_socket.getsockname()}\n")

    # Get the username to be stored in the server,
    # Send username and p2p port
    username = input("Enter your username: ")
    clientSocket.send(f"{username},{p2p_socket.getsockname()[1]}".encode())
    server_response = clientSocket.recv(1024).decode().strip()
    while server_response == "REJECTED":
        username = input(
            "\nUsername not avialable. Try a different username.\nEnter your username: "
        )
        clientSocket.send(f"{username},{p2p_socket.getsockname()[1]}".encode())
        server_response = clientSocket.recv(1024).decode().strip()

    print("Valid username. Connected to Server")

    # Share messages between processes
    conn1, conn2 = Pipe()

    # Start message exchange with server in a sepaprate process
    server_handler_process = Process(
        target=server_connection_handler,
        args=(clientSocket, sys.stdin.fileno(), conn1),
    )
    server_handler_process.start()

    # Listen to incomming client connection requests in a separate process
    p2p_handler_process = Process(
        target=p2p_connection_handler,
        args=(p2p_socket, sys.stdin.fileno(), conn2),
    )
    p2p_handler_process.start()

    # Make main process wait for server_handler_process
    server_handler_process.join()

    # If the server_handler_process finishes execution, kill the p2p client connection handler
    p2p_handler_process.kill()

    # Close client socket and p2p socket
    clientSocket.close()
    p2p_socket.close()


if __name__ == "__main__":
    runClient()

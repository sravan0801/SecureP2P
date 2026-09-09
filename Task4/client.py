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

# Module to generate random numbers
import random

# Terminal Utils
from termios import tcflush, TCIOFLUSH

# Module for AES encryption and decryption
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# For calculating the padding length
from math import ceil

# Available options for client
COMMANDS = {
    "get": "Get a list of connected users.",
    "connect <username>": "Connect to a specific user.",
    "END": "End server session.",
    "EOM": "End messaging session.",
}

# Diffie Hellman default Params
p = 1
g = 1


def print_help_message():
    """
    Utility functions that print the commands available
    """
    print("\nAvailable Commands: ")
    for command, desc in COMMANDS.items():
        print(f"\t{command}: {desc}")
    print("\n")


def generate_key_pair() -> tuple:
    """
    Function to compute public key using Diffie Hellman Key exchange

    Returns:
        (public_key, private_key)
    """
    global p, g
    print("Generating Key Pairs")
    private_key = random.randrange(1, p - 1)
    return pow(g, private_key, p), private_key


def shared_key_generator(peer_public_key: int, private_key: int) -> int:
    """
    Function to compute shared key

    Parameters:
        peer_public_key (int): public key of the peer
        private_key (int): private key of current host

    Returns:
        Shared Key generated using Diffie Hellman key exchange
    """
    global p, g
    print("Generating Shared Key")
    return pow(peer_public_key, private_key, p)


def aes_key_generator(shared_key: int) -> tuple:
    """
    Function to compute aes key
    """
    # Set shared_key as seed
    random.seed(shared_key)

    # Generate a key of required size
    aes_key = random.randbytes(32)
    init_vector = random.randbytes(16)
    return (aes_key, init_vector)


# TODO:
# 1. Print username instead of the IP when exchanging messages
# 2. Message exchange btw the same client does not work
def p2p_message_exchange_handler(peer_socket: socket.socket, cipher: Cipher) -> None:
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
            # Use \n as separator for padding and message
            message = "\n" + input("send> ")
            encryptor = cipher.encryptor()
            padding_len = ceil(len(message) / 128) * 128

            # add padding and encrypt text
            cipher_text = (
                encryptor.update(message.encode().zfill(padding_len))
                + encryptor.finalize()
            )
            peer_socket.send(cipher_text)
            if message == "\nEOM":
                break
        if peer_socket in rlist:
            # Decrypt received cipher text
            cipher_text = peer_socket.recv(1024)
            decryptor = cipher.decryptor()

            # Decrypt and remove padding
            plain_text = (decryptor.update(cipher_text) + decryptor.finalize()).decode()
            plain_text = plain_text[plain_text.index("\n") + 1 :]
            if plain_text == "EOM" or plain_text == "":
                print("\r\nUser closed connection\n")
                break
            print(f"\rrecv[ChiperText]> {cipher_text}\n", end="")
            print(f"\rrecv[PlainText ]> {plain_text}\nsend> ", end="")


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

        message_queue.send(0)

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

            # Shared key(Ksa) generation using Diddie-Hellman Protocol at peer got the connection request
            public_key, private_key = generate_key_pair()
            peer_pub_key = peer_socket.recv(1024).decode()
            peer_socket.send(str(public_key).encode())
            shared_key = shared_key_generator(int(peer_pub_key), private_key)

            print(f"Private Key: {private_key}")
            print(f"Public key: {public_key}")
            print(f"Public key of Peer: {peer_pub_key}")
            print(f"Shared key: {shared_key}")

            aes_key, init_vector = aes_key_generator(shared_key)
            print(f"AES key: {aes_key.hex(sep=' ')}")
            print(f"AES initialization vector: {init_vector.hex(sep=' ')}")
            cipher = Cipher(
                algorithm=algorithms.AES256(aes_key), mode=(modes.CBC(init_vector))
            )
            p2p_message_exchange_handler(peer_socket, cipher)
        else:
            peer_socket.send("REFUSED".encode())

        # close peer socket
        peer_socket.close()

        # Resume the server_connection_handler process
        print("\rEnter Option: ", end="", flush=True)
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

                # Shared key(Ksa) generation using Diddie-Hellman Protocol at peer who initiated the connection
                public_key, private_key = generate_key_pair()
                peer_socket.send(str(public_key).encode())
                peer_pub_key = peer_socket.recv(1024).decode()
                shared_key = shared_key_generator(int(peer_pub_key), private_key)

                print(f"Private Key: {private_key}")
                print(f"Public key: {public_key}")
                print(f"Peer public key: {peer_pub_key}")
                print(f"Shared key: {shared_key}")

                aes_key, init_vector = aes_key_generator(shared_key)
                print(f"AES key: {aes_key.hex(sep=' ')}")
                print(f"AES initialization vector: {init_vector.hex(sep=' ')}")
                cipher = Cipher(
                    algorithm=algorithms.AES256(aes_key), mode=(modes.CBC(init_vector))
                )
                p2p_message_exchange_handler(peer_socket, cipher)
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
    if "P" not in os.environ or "Q" not in os.environ:
        print(
            "Diffie Hellman public parameters are not set. Please add the parameters to the .env file in the project root dir and run 'pipevn shell' command to load the env variables."
        )
        sys.exit(1)

    p = int(os.environ["P"])
    g = int(os.environ["Q"])
    print(f"Public Diffie Hellman Params\nPrime: {p}\nGenerator: {g}\n")
    runClient()

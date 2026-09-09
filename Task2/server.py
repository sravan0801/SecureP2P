# Socket module
import socket

# Module used to set signal handlers
import signal

# Module used to create parallel Processes and share state between processes
from multiprocessing import Process, Manager
from multiprocessing.managers import DictProxy

# Module used to make the socket non blocking
import select

# Module to serialize dict
import json

# Server Listen port number
SERVER_PORT = 11000

# This vairable is set to 1, if SIGINT is received
# The while loop runs only if this flag is not equal to 1
EXIT_FLAG = 0


# Signal handler that will set the exit flag as 1
def signalHandler(sig, frame):
    global EXIT_FLAG
    EXIT_FLAG = 1
    print("SIGINT received, closing server and client sockets")


def handle_client(connectionFD: socket.socket, active_users: DictProxy) -> None:
    """
    Function to handles client messages

    Parameters:
        connectionFD (socket.socket): socket created after connecting with client

    Returns:
        None
    """
    global EXIT_FLAG

    # Get client IP
    client_ip, _ = connectionFD.getpeername()

    # Fetch the username till clients gives a unique username
    message = connectionFD.recv(1024)
    (username, port) = message.decode().strip().split(",")
    while username == "" or username in active_users.keys():
        connectionFD.send("REJECTED".encode())
        message = connectionFD.recv(1024)
        (username, port) = message.decode().strip().split(",")

    # Send ACCEPTED Message when the given username is unique
    connectionFD.send("ACCEPTED".encode())

    # Store the username, ip and port details
    active_users[username] = (client_ip, port)
    print(f"Current active users: {active_users.items()}")

    # Continue to send messages until client closes connection or
    # if server receives SIGINT, close the client connection
    while EXIT_FLAG == 0:
        # Peek client socket every 1 second
        if select.select([connectionFD], [], [], 1)[0] == []:
            continue

        message = connectionFD.recv(1024)
        message = message.decode().strip()
        print(f"INFO: {client_ip} -> {message}")

        # If the message is about getting connected user details then the details are sentto the client
        if message == "get":
            connectionFD.send(json.dumps(active_users.copy()).encode())

        # If the message in recv is empty, the client has closed the connection
        elif message == "":
            print(f"Client({client_ip},{port}) closed connection")
            break

    # Remove client from the active_users dict
    active_users.pop(username)
    print(f"Current active users: {active_users.items()}")
    connectionFD.close()


def run_server() -> None:
    """
    Function to create a socket and listen to incomming connection requests
    """
    global SERVER_PORT

    # Set the signal handler
    signal.signal(signal.SIGINT, handler=signalHandler)

    # Create a TCP socket
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Set socket option to reuse address
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Assign IP address and port number to socket
    serverSocket.bind(("", SERVER_PORT))

    # Listen for connection requests
    serverSocket.listen(50)
    print(
        f"Server listening on: {serverSocket.getsockname()[0]}:{serverSocket.getsockname()[1]}"
    )

    # Create manager object to share variables between processes
    manager = Manager()
    # Create a shared variable containing active users
    active_users = manager.dict()

    while EXIT_FLAG == 0:
        # Peek listening socket every 1 second
        if select.select([serverSocket], [], [], 1)[0] == []:
            # No incoming connection requests
            # Check if the EXIT_FLAG is still zero
            continue

        # Accept connection request
        connectionFD, _ = serverSocket.accept()

        # Create a new Thread that exchanges messages with client
        client_thread = Process(target=handle_client, args=(connectionFD, active_users))

        # Start the process
        client_thread.start()

    print("Closing server socket")
    serverSocket.close()


if __name__ == "__main__":
    run_server()

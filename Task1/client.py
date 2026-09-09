# Socket module
import socket

# Module used to set signal handlers
import signal

# Module to make sockets reads non blocking
import select

# Socket timeout
TIMEOUT = 5

# This vairable is set to 1, if SIGINT is received
# The while loop runs only if this flag is not equal to 1
EXIT_FLAG = 0


# Signal handler that will set the exit flag as 1
def signalHandler(sig, frame):
    global EXIT_FLAG
    EXIT_FLAG = 1
    print("SIGINT received, closing client socket")


def getResultFromServer(clientSocket: socket.socket) -> None:
    global TIMEOUT, EXIT_FLAG

    while EXIT_FLAG == 0:
        # Get expression to evaluate
        expression = input("Enter expression to evaluate: ")

        # Client exit
        if expression.strip().lower() == "end":
            break

        # Send expression to server
        clientSocket.send(expression.encode())

        # Wait for TIMEOUT seconds for the server response
        ready = select.select([clientSocket], [], [], TIMEOUT)

        # Did not receive any response within TIMEOUT seconds
        if ready[0] == []:
            print("Error: Timeout. No response from server")
            break

        # Receive message from server
        message = clientSocket.recv(100).decode()

        # If message is empty, server has closed the connection
        if message == "":
            print("Error: Server closed connection")
            break

        # Print expression result
        print(f"Result from server: {message}")


def runClient() -> None:
    # Set signal handler that will exit while loops
    signal.signal(signal.SIGINT, handler=signalHandler)

    # Create a TCP socket
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Connect to the server
    clientSocket.connect(("", 11000))

    # Get result from server
    getResultFromServer(clientSocket)

    # Close client socket
    clientSocket.close()


if __name__ == "__main__":
    runClient()

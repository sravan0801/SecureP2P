# Socket module
import socket

# Module used to set signal handlers
import signal

# Module used to create parallel Processes
from multiprocessing import Process

# Module used to make the socket non blocking
import select

# Server Listen port number
SERVER_PORT = 11000

# Maps a string operator to a function that performs the operation
OPERATIONS_MAP = {
    "+": lambda num1, num2: num1 + num2,
    "-": lambda num1, num2: num1 - num2,
    "%": lambda num1, num2: num1 % num2,
    "*": lambda num1, num2: num1 * num2,
    "x": lambda num1, num2: num1 * num2,
    "/": lambda num1, num2: num1 / num2,
}

# This vairable is set to 1, if SIGINT is received
# The while loop runs only if this flag is not equal to 1
EXIT_FLAG = 0


# Signal handler that will set the exit flag as 1
def signalHandler(sig, frame):
    global EXIT_FLAG
    EXIT_FLAG = 1
    print("SIGINT received, closing server and client sockets")


def format_input_expression(input: str) -> list:
    """
    Validate and format input

    Parameters:
        input (str): input algebra expression as a string

    Returns:
        list: format [operand, operator, operand ....]
    """
    tokens = input.strip().split(" ")
    formatted_expression = list()

    for index in range(0, len(tokens)):
        if index % 2 == 0:
            formatted_expression.append(float(tokens[index]))
            continue

        if tokens[index] not in OPERATIONS_MAP:
            raise SyntaxError(
                "Expression can only contain numbers and binary operators"
            )

        formatted_expression.append(tokens[index])
    return formatted_expression


def evaulate_expression(formatted_expression: list) -> float:
    """
    Function to evaluate a valid formatted expression

    Parameters:
        formatted_expression (list): output of format_input_expression() function

    Result:
        float: float result after evaluating expression
    """

    operator_index = 1
    # Evaluate all *, / and % operations from left to right
    while operator_index < len(formatted_expression):

        # Skip current operator and go to next operator
        if formatted_expression[operator_index] not in ["*", "/", "%"]:
            operator_index += 2
            continue

        # Get result of a single operator
        formatted_expression[operator_index - 1] = OPERATIONS_MAP[
            formatted_expression[operator_index]
        ](
            formatted_expression[operator_index - 1],
            formatted_expression[operator_index + 1],
        )

        # Pop operator and operand that are evaluated
        formatted_expression.pop(operator_index)
        formatted_expression.pop(operator_index)

    # Evaluate all + and - operations
    operator_index = 1
    while len(formatted_expression) > 1:
        # Get result of a single operator
        formatted_expression[operator_index - 1] = OPERATIONS_MAP[
            formatted_expression[operator_index]
        ](
            formatted_expression[operator_index - 1],
            formatted_expression[operator_index + 1],
        )

        # Pop operator and operand that are evaluated
        formatted_expression.pop(operator_index)
        formatted_expression.pop(operator_index)

    return formatted_expression[0]


def handle_client(connectionFD: socket.socket) -> None:
    """
    Function to handles client messages

    Parameters:
        connectionFD (socket.socket): socket created after connecting with client

    Returns:
        None
    """
    global EXIT_FLAG

    # Get client IP:Port
    client_info = connectionFD.getpeername()

    # Continue to send messages until client closes connection or
    # if server receives SIGINT, close the client connection
    while EXIT_FLAG == 0:
        # Peek client socket every 1 second
        if select.select([connectionFD], [], [], 1)[0] == []:
            continue

        message = connectionFD.recv(1024)
        message = message.decode().strip()

        # If the message in recv is empty, the client has closed the connection
        if message == "":
            print(f"Client({client_info}) closed connection")
            break

        print(f"Received message from client({client_info}): ", message)

        try:
            formatted_expression = format_input_expression(message)
            connectionFD.send(str(evaulate_expression(formatted_expression)).encode())

        except (SyntaxError, ValueError, KeyError, IndexError):
            print(f"Input format error client{client_info}: {message}")
            connectionFD.send("Syntax Error".encode())

        except ZeroDivisionError:
            print(f"Zero Division error client{client_info}: {message}")
            connectionFD.send("Zero Divison Error".encode())

    print(f"Closing client({client_info}) socket")
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
    serverSocket.listen(10)
    print(
        f"Server listening on: {serverSocket.getsockname()[0]}:{serverSocket.getsockname()[1]}"
    )

    while EXIT_FLAG == 0:
        # Peek listening socket every 1 second
        if select.select([serverSocket], [], [], 1)[0] == []:
            # No incoming connection requests
            # Check if the EXIT_FLAG is still zero
            continue

        # Accept connection request
        connectionFD, _ = serverSocket.accept()

        # Create new Process that exchanges messages with client
        handler = Process(target=handle_client, args=(connectionFD,))

        # Start the process
        handler.start()

    print("Closing server socket")
    serverSocket.close()


if __name__ == "__main__":
    run_server()

# SecureP2P

A four-part socket-programming assignment that incrementally builds a peer-to-peer
chat application, starting from a simple TCP client/server and ending with a
directory-server-assisted P2P chat whose messages are end-to-end encrypted with
AES-256.

Everything is plain Python 3 standard library, except Task 4 which uses the
`cryptography` package for AES. Each task lives in its own folder with a
`server.py` and `client.py`, and Tasks 2–4 include a Wireshark capture
(`.pcap`) taken while the programs were running.

---

## What is implemented

### Task 1 — Concurrent TCP arithmetic server
- TCP server on port `11000` that evaluates arithmetic expressions sent as text
  (e.g. `3 + 4 * 2`).
- Each client is served in its own `multiprocessing.Process`, so multiple
  clients are handled concurrently.
- Supports `+ - * x / %` with correct operator precedence (`* / %` before
  `+ -`), left-to-right evaluation.
- Graceful shutdown on `SIGINT`; non-blocking accept/recv via `select`.
- Server replies with `Syntax Error` for malformed input and
  `Zero Divison Error` for division by zero.
- Client reads expressions from stdin, sends them, waits up to 5 s for a reply,
  and exits on `end`.

### Task 2 — Directory server + plaintext P2P chat
- **Server** keeps a shared registry of active users
  (`username -> (ip, p2p_port)`) using `multiprocessing.Manager`.
  - On connect, the client sends `username,p2p_port`; the server rejects empty or
    duplicate usernames (`REJECTED`) until a unique one is given (`ACCEPTED`).
  - Responds to `get` with the JSON list of currently connected users.
  - Drops the user from the registry when the connection closes.
- **Client** runs three pieces concurrently:
  - a *server handler* process for the `get` / `connect <username>` / `end`
    command loop,
  - a *P2P listener* process that accepts incoming peer connections and prompts
    the user to accept/refuse (`Y/n`),
  - the P2P message-exchange loop itself.
  - Peers talk **directly** to each other (not through the server). Messages are
    sent in **plaintext**. `EOM` ends a chat session; `end` disconnects from the
    server.
- `Task2.pcap` shows the messages travelling in clear text.

### Task 3 — Diffie–Hellman key agreement
- Same architecture as Task 2, plus a **Diffie–Hellman key exchange** performed
  by the two peers immediately after a connection is accepted:
  - each side generates a private/public key pair from the public parameters
    `P` (prime) and `G` (generator),
  - public keys are swapped and a shared secret is computed,
  - the shared secret seeds a PRNG that derives a 32-byte **AES key** and a
    16-byte **IV**.
- Keys, shared secret and derived AES material are printed to the console for
  inspection.
- `P` and `G` are read from the environment (`P` and `Q`); the client refuses to
  start if they are not set.
- Messages are still sent in plaintext at this stage — `Task3.pcap` shows the
  key exchange followed by clear-text messages.

### Task 4 — AES-256 encrypted P2P chat
- Builds on Task 3: the derived key/IV are used to create an
  **AES-256-CBC cipher** (`cryptography` package).
- Every P2P message is padded, encrypted before sending and decrypted on
  receipt. The chat UI prints both the ciphertext and the recovered plaintext.
- `Task4.pcap` shows the P2P payloads are now unreadable ciphertext, while the
  directory-server traffic (`get`, user list) remains plaintext.

---

## Requirements

- Python 3.9+
- Task 4 only: `pip install cryptography`
- A POSIX terminal (the client uses `termios` / `select` on stdin).

---

## How to run

All commands are run from inside the relevant task folder. Start the server
first, then one or more clients (use a separate terminal per client).

### Task 1
```bash
cd Task1
python3 server.py                 # terminal 1
python3 client.py                 # terminal 2+
# then type expressions, e.g.:  12 + 3 * 4
# type 'end' to quit the client, Ctrl+C to stop the server
```

### Task 2
```bash
cd Task2
python3 server.py                 # terminal 1
python3 client.py                 # terminal 2  -> enter a username
python3 client.py                 # terminal 3  -> enter another username

# in a client:
get                               # list connected users
connect <username>                # start a P2P chat with that user
#   the other side gets a Y/n prompt to accept
EOM                               # end the chat session
end                               # disconnect from the server
```

### Task 3
Provide the Diffie–Hellman parameters via the `P` and `Q` environment variables
(`P` = prime, `Q` = generator).
```bash
cd Task3
python3 server.py                                 # terminal 1
P=23 Q=5 python3 client.py                        # terminal 2
P=23 Q=5 python3 client.py                        # terminal 3
# use larger real DH parameters for meaningful key sizes

# same commands as Task 2: get / connect <username> / EOM / end
# on 'connect', both peers print their DH keys, shared secret and AES key/IV
```

### Task 4
```bash
pip install cryptography
cd Task4
python3 server.py                                 # terminal 1
P=23 Q=5 python3 client.py                        # terminal 2
P=23 Q=5 python3 client.py                        # terminal 3

# get / connect <username> / EOM / end
# during a chat each line is shown as ciphertext on the wire and
# decrypted plaintext on the receiver
```

### Inspecting the captures
Open `Task2/Task2.pcap`, `Task3/Task3.pcap` or `Task4/Task4.pcap` in Wireshark
and follow the TCP streams to compare plaintext (Tasks 2–3) vs. encrypted
(Task 4) P2P traffic.

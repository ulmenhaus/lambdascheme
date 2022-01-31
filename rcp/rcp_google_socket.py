>>> import socket
>>>
>>> sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
>>> sock.connect(("www.google.com", 80))
>>>
>>> sock.send(b"GET / HTTP/1.1\n\n")
>>> print(sock.recv(100).split(b"\n")[0].strip().decode("utf-8"))

HTTP/1.1 200 OK

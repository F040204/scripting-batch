from smbprotocol.connection import Connection
from smbprotocol.session import Session

conn = Connection("test", "172.16.11.107", 445)
conn.connect()

session = Session(conn, username="felipe@OrexChile01", password="El.040204")
session.connect()
print("session id:", session.session_id)

import subprocess
import sys
from base64 import standard_b64encode
import click
import sqlite3
import datetime
import os


def serialize_gr_command(**cmd):
    payload = cmd.pop("payload", None)
    cmd = ",".join(f"{k}={v}" for k, v in cmd.items())
    ans = []
    w = ans.append
    w(b"\033_G"), w(cmd.encode("ascii"))
    if payload:
        w(b";")
        w(payload)
    w(b"\033\\")
    return b"".join(ans)


def write_chunked(**cmd):
    data = standard_b64encode(cmd.pop("data"))
    while data:
        chunk, data = data[:4096], data[4096:]
        m = 1 if data else 0
        sys.stdout.buffer.write(serialize_gr_command(payload=chunk, m=m, **cmd))
        sys.stdout.flush()
        cmd.clear()


def execute_command(command: list[str], stdin=subprocess.PIPE) -> bytes:
    return subprocess.run(
        command, stdin=stdin, stdout=subprocess.PIPE, text=False
    ).stdout


@click.group()
def main():
    pass


connection = sqlite3.connect("bufer.db")
cursor = connection.cursor()
cursor.execute("""--sql
        CREATE TABLE IF NOT EXISTS bufer(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            binary_data BLOB,
            date_time REAL,
            mime_types TEXT
        );
""")
cursor.execute("""--sql
        CREATE TABLE IF NOT EXISTS types(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            subname TEXT,
            parametr TEXT,
            argument TEXT
        );
""")
cursor.execute("""--sql
        CREATE TABLE IF NOT EXISTS  bufer_to_types(
            id_type INTEGER,
            id_bufer INTEGER
        );
""")
connection.commit()


@main.command()
def store():
    data_in_stdin = sys.stdin.buffer.read()
    data_in_system_bufer = execute_command(["wl-paste"])
    types = (
        execute_command(["wl-paste", "-l"]).decode(encoding="utf-8")[:-1].split("\n")
    )
    n_types = []
    for element in types:
        elements = element.split(";")
        mime_types = elements[0].split("/")
        if len(mime_types) == 1:
            continue
        if len(elements) == 1:
            parametrs = [None, None]
        else:
            parametrs = elements[1].split("=")
        n_types.append(
            {
                "type": mime_types[0],
                "subtype": mime_types[1],
                "parametr": parametrs[0],
                "argument": parametrs[1],
            }
        )
    # sys.stdout.write(execute_command(""))
    # execute_command(["wl-copy"], sys.stdin)
    if 1:
        print(n_types)
        if "image/png" in types:
            write_chunked(a="T", f=100, data=data_in_stdin)
        else:
            print(data_in_stdin)
    # sys.stdout.buffer.write(sys.stdin.buffer.read())
    cursor.execute("--sql SELECT * FROM bufer;")
    results = cursor.fetchall()
    if len(results) > 30:
        pass
    data_in_stdin_equal_data_in_db: bool = False
    for result in results:
        if result[1] == data_in_stdin:
            data_in_stdin_equal_data_in_db = True
            break
    if data_in_stdin_equal_data_in_db:
        pass
    else:
        cursor.execute("""--sql
            INSERT INTO bufer (binary_data, date_time, mime_types ) VALUES (?, ?, ?)""",
            (data_in_stdin, datetime.datetime.now().timestamp(), n_types.__str__()),
        )
    connection.commit()


@main.command()
def pick():
    id = sys.stdin.buffer.read()


@main.command()
def get_history():
    cursor.execute("--sql SELECT * FROM bufer;")
    results = cursor.fetchall()
    history = ""
    for result in results:
        history = (
            history
            + result[0].__str__()
            + ". "
            + result[1].__str__()
            + "\t| "
            + datetime.datetime.fromtimestamp(result[2]).isoformat()
            + "\n"
        )
    sys.stdout.buffer.write(history.encode("utf-8"))


@main.command()
def remove():
    id = sys.stdin.buffer.read()
    cursor.execute("""--sql
                   SELECT * FROM bufer
                   WHERE id = ?;
                   """, (id))
    print(f"Removed {len(cursor.fetchall())} items.")
    cursor.execute("""--sql
                   DELETE FROM bufer
                   WHERE id = ?;
                   """, (id))


if __name__ == "__main__":
    main()

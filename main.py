#!/usr/bin/python3

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


def execute_command(command: list[str], input_in=None, stdin=subprocess.PIPE) -> bytes:
    if input_in is not None:
        return subprocess.run(
            command, stdout=subprocess.PIPE, text=False, input=input_in
        ).stdout
    else:
        return subprocess.run(
            command, stdin=stdin, stdout=subprocess.PIPE, text=False
        ).stdout


@click.group()
def main():
    pass


connection = sqlite3.connect("bufer.db")
cursor = connection.cursor()
cursor.execute(
    """--sql
        CREATE TABLE IF NOT EXISTS bufer(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            binary_data BLOB UNIQUE,
            date_time REAL
        );
"""
)
cursor.execute(
    """--sql
        CREATE TABLE IF NOT EXISTS types(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            subname TEXT,
            parametr TEXT,
            argument TEXT,
            UNIQUE (name, subname, parametr, argument) ON CONFLICT REPLACE
        );
"""
)
cursor.execute(
    """--sql
        CREATE TABLE IF NOT EXISTS  bufer_to_types(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            types_id INTEGER NOT NULL,
            bufer_id INTEGER NOT NULL,
            FOREIGN KEY(types_id)  REFERENCES types(id) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY(bufer_id)  REFERENCES bufer(id) ON DELETE CASCADE ON UPDATE CASCADE,
            UNIQUE (types_id, bufer_id) ON CONFLICT REPLACE
        );
"""
)
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
        n_types.append((mime_types[0], mime_types[1], parametrs[0], parametrs[1]))
    # sys.stdout.write(execute_command(""))
    # execute_command(["wl-copy"], sys.stdin)
    if 1:
        print(n_types)
        if "image/png" in types:
            write_chunked(a="T", f=100, data=data_in_stdin)
        else:
            pass
            #print(data_in_stdin)
    # sys.stdout.buffer.write(sys.stdin.buffer.read())
    limit = 30
    cursor.execute(
        """--sql
            DELETE FROM bufer
            WHERE id NOT IN (
                SELECT id
                FROM bufer
                WHERE id IN
                    (SELECT id
                    FROM bufer
                    ORDER BY date_time DESC
                    LIMIT ?));
                   """,
        (limit,),
    )
    connection.commit()
    date_time = datetime.datetime.now().timestamp()
    cursor.execute(
        """--sql
            REPLACE INTO bufer (binary_data, date_time) VALUES (?, ?)""",
        (data_in_stdin, date_time),
    )
    cursor.executemany(
        """--sql
            REPLACE INTO types (name, subname, parametr, argument) VALUES (?, ?, ?, ?)""",
        n_types,
    )
    nn_types = []
    for n_type in n_types:
        nn_types.append((date_time, n_type[0], n_type[1], n_type[2], n_type[3],
                         date_time, n_type[0], n_type[1], n_type[2], n_type[3]))
    print()
    cursor.executemany(
        """--sql
            REPLACE INTO bufer_to_types (bufer_id, types_id) VALUES (
                (
                    SELECT bufer.id FROM bufer, types
                    WHERE bufer.date_time = ? AND types.name = ? AND types.subname = ? AND types.parametr = ? AND types.argument = ?
                ), (
                    SELECT types.id FROM bufer, types
                    WHERE bufer.date_time = ? AND types.name = ? AND types.subname = ? AND types.parametr = ? AND types.argument = ?
                )
            );""",
        nn_types,
    )
    connection.commit()


@main.command()
def pick():
    i = int(sys.stdin.buffer.read().decode("utf-8")[:-1])
    cursor.execute(
        """--sql
                   SELECT binary_data FROM bufer
                   WHERE id = ?;""",
        (i,),
    )
    execute_command(["wl-copy"], input_in=cursor.fetchone()[0])


@main.command()
def get_data():
    i = int(sys.stdin.buffer.read().decode("utf-8")[:-1])
    cursor.execute(
        """--sql
                   SELECT binary_data FROM bufer
                   WHERE id = ?;""",
        (i,),
    )
    sys.stdout.write(cursor.fetchone()[0])


@main.command()
def get_time():
    i = int(sys.stdin.buffer.read().decode("utf-8")[:-1])
    cursor.execute(
        """--sql
                   SELECT date_time FROM bufer
                   WHERE id = ?;""",
        (i,),
    )
    sys.stdout.write(
        datetime.datetime.fromtimestamp(cursor.fetchone()[0]).__str__().encode("utf-8")
    )


@main.command()
def get_list():
    cursor.execute(
        """--sql
                   SELECT * FROM bufer
                   ORDER BY date_time;"""
    )
    results = cursor.fetchall()
    output: str = ""

    for indificator, binary_data, date_time in results:
        cursor.execute(
            """--sql
                   SELECT types.name FROM bufer_to_types, types
                   WHERE bufer_to_types.bufer_id = ? AND types.id = bufer_to_types.types_id;
                   """,
            (indificator,),
        )
        names = []
        for (name,) in cursor.fetchall():
            names.append(name)
        if "text" in names:
            output = output + binary_data.decode("utf-8").replace("\n", "").replace(
                "\t", "󰌒"
            )
        else:
            output = output + names.__str__()
        output = output + "\n"
    output = output + f"Count: {len(results)}" + "\n"
    sys.stdout.buffer.write(output.encode("utf-8"))


@main.command()
def restore():
    pass


@main.command()
def get_last():
    pass


@main.command()
def remove():
    id = int(sys.stdin.buffer.read())
    cursor.execute(
        """--sql
                   SELECT COUNT(*) FROM bufer
                   WHERE id = ?;
                   """,
        (id,),
    )
    print(f"Removed {cursor.fetchall()[0]} items.")
    cursor.execute(
        """--sql
                   DELETE FROM bufer
                   WHERE id = ?;
                   """,
        (id,),
    )
    connection.commit()


if __name__ == "__main__":
    main()

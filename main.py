#!/usr/bin/python3

import datetime
import os
import sqlite3
import subprocess
import sys
import pathlib
from base64 import standard_b64encode

import click


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
@click.option(
    "-p",
    "--path-sqlite",
    "path",
    default="~/.config/clipmanager/bufer.db",
    help="path to sqlite database",
)
@click.pass_context
def main(ctx, path):
    path = pathlib.Path(path)
    ctx.ensure_object(dict)
    ctx.obj["path"] = path
    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    ctx.obj["connection"] = connection
    ctx.obj["cursor"] = cursor
    cursor.execute(
        """--sql
            CREATE TABLE IF NOT EXISTS bufer(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                binary_data BLOB UNIQUE,
                date_time REAL UNIQUE
            );
    """
    )
    cursor.execute(
        """--sql
            CREATE TABLE IF NOT EXISTS types(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subname TEXT NOT NULL,
                parametr TEXT NOT NULL,
                argument TEXT NOT NULL,
                UNIQUE (name, subname, parametr, argument) ON CONFLICT REPLACE
            );
    """
    )
    cursor.execute(
        """--sql
            CREATE TABLE IF NOT EXISTS  bufer_to_types(
                types_id INTEGER NOT NULL,
                bufer_id INTEGER NOT NULL,
                FOREIGN KEY(types_id)  REFERENCES types(id) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY(bufer_id)  REFERENCES bufer(id) ON DELETE CASCADE ON UPDATE CASCADE,
                UNIQUE (types_id, bufer_id) ON CONFLICT REPLACE
            );
    """
    )
    connection.commit()


@main.command()
@click.option(
    "-l",
    "--max-length",
    "length",
    default=30,
    type=click.types.INT,
    help="maximum number of entries in the buffer",
)
@click.pass_context
def store(ctx, length):
    """Store data from STDIN to sqlite database"""
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
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
            parametrs = ["", ""]
        else:
            parametrs = elements[1].split("=")
        n_types.append((mime_types[0], mime_types[1], parametrs[0], parametrs[1]))
    limit = length
    cursor.execute(  # delete old data from buffer
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
    cursor.execute(  # insert binary_data
        """--sql
            INSERT OR REPLACE INTO bufer (binary_data, date_time) VALUES (?, ?)""",
        (data_in_stdin, date_time),
    )
    cursor.executemany(  # insert types
        """--sql
            INSERT  OR IGNORE INTO  types (name, subname, parametr, argument) VALUES (?, ?, ?, ?)""",
        n_types,
    )
    nn_types = []
    is_not_text = True
    for n_type in n_types:
        if n_type[0] == "text":
            is_not_text = False
        nn_types.append((date_time, n_type[0], n_type[1], n_type[2], n_type[3]))
    cursor.executemany(  # insert relations
        """--sql
            INSERT OR IGNORE INTO bufer_to_types (bufer_id, types_id) VALUES (
                (
                    SELECT id FROM bufer
                    WHERE date_time = ?
                    LIMIT 1
                ), (
                    SELECT id FROM types
                    WHERE name = ? AND
                       subname = ? AND
                      parametr = ? AND
                      argument = ?
                    LIMIT 1
                )
            );""",
        nn_types,
    )
    connection.commit()
    if is_not_text:
        cursor.execute(  # search id
            """--sql 
                       SELECT id FROM bufer
                       WHERE date_time = ?
                       LIMIT 1
                       """,
            (date_time,),
        )
        indificator = cursor.fetchone()[0]
        execute_command(["notify-send", "--app-name=clipmanager","Copied", f"id: {indificator}, types: {types.__str__()}"]) 

@main.command()
@click.pass_context
def pick(ctx):
    """Copies an entry with the specified index to the system clipboard"""
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
    i = int(sys.stdin.buffer.read().decode("utf-8").split(".")[0])
    cursor.execute(
        """--sql
                   SELECT binary_data FROM bufer
                   WHERE id = ?;""",
        (i,),
    )
    execute_command(["wl-copy"], input_in=cursor.fetchone()[0])


@main.command()
@click.pass_context
def get_data(ctx):
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
    i = int(sys.stdin.buffer.read().decode("utf-8")[:-1])
    cursor.execute(
        """--sql
                   SELECT binary_data FROM bufer
                   WHERE id = ?;""",
        (i,),
    )
    sys.stdout.write(cursor.fetchone()[0])


@main.command()
@click.pass_context
def get_time(ctx):
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
    i = int(sys.stdin.buffer.read().decode("utf-8")[:-1])
    cursor.execute(
        """--sql
                   SELECT date_time FROM bufer
                   WHERE id = ?;""",
        (i,),
    )
    sys.stdout.write(
        datetime.datetime.fromtimestamp(cursor.fetchone()[0])
        .isoformat()
        .__str__()
        .encode("utf-8")
    )


@main.command()
@click.pass_context
def get_list(ctx):
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
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
        output = output + f"{indificator}. "
        if "text" in names:
            output = output + binary_data.decode("utf-8").replace("\n", "").replace(
                "\t", "󰌒"
            )
        else:
            output = (
                output
                + names.__str__()
                + datetime.datetime.fromtimestamp(date_time).isoformat(" ")
            )
        output = output + "\n"
    sys.stdout.buffer.write(output.encode("utf-8"))


@main.command()
@click.pass_context
def restore(ctx):
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]


@main.command()
@click.pass_context
def get_last(ctx):
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]


@main.command()
@click.pass_context
def swap(ctx):
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]


@main.command()
@click.pass_context
def remove(ctx):
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
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
    main(obj={})

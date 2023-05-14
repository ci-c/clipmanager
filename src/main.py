#!/usr/bin/python3

import datetime
import os
import sqlite3
import subprocess
import sys
import pathlib
from base64 import standard_b64encode
import configparser
import click
import string


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
@click.option(
    "-c",
    "--path-config",
    "path_config",
    default="~/.config/clipmanager/config.ini",
    help="path to config.ini",
)
@click.pass_context
def main(ctx, path, path_config):
    path_config = pathlib.Path(path_config)
    config = configparser.ConfigParser()
    config.read(path_config)
    path = pathlib.Path(path)
    ctx.ensure_object(dict)
    ctx.obj["path"] = path
    ctx.obj["config"] = config
    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    ctx.obj["connection"] = connection
    ctx.obj["cursor"] = cursor
    cursor.execute(  # create table "bufer"
        """--sql
            CREATE TABLE IF NOT EXISTS bufer(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                binary_data BLOB UNIQUE,
                date_time REAL UNIQUE
            );
    """
    )
    cursor.execute(  # create table "types"
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
    cursor.execute(  # create table "bufer_to_types"
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
    limit = length - 1
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
        execute_command(
            [
                "notify-send",
                "--app-name=clipmanager",
                "Copied",
                f"id: {indificator}, types: {types.__str__()}",
            ]
        )


@main.command()
@click.pass_context
def pick(ctx):
    """Copies an entry with the specified index to the system clipboard"""
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
    index = int(sys.stdin.buffer.read().decode("utf-8").split(".")[0])
    cursor.execute(
        """--sql
                   SELECT binary_data FROM bufer
                   WHERE id = ?;""",
        (index,),
    )
    execute_command(["wl-copy"], input_in=cursor.fetchone()[0])


@main.command()
@click.option(
    "-f",
    "--format",
    "format",
    default="{id}. {data}",
    help="Sets the formatting of each string using python `str.format()`, where the following variables can be used: `id`, `data`, `data_time`, `types'.",
)
@click.pass_context
def get(ctx, format):
    """get item by id"""
    if format == None:
        format = ctx.obj["config"]["default"]["format list"]
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
    index = int(sys.stdin.buffer.read().decode("utf-8").split(".")[0])
    cursor.execute(
        """--sql
                   SELECT * FROM bufer
                   WHERE id = ?;""",
        (index,),
    )
    result = cursor.fetchone()
    output: bytes = b""

    
    cursor.execute(  # get type's names
            """--sql
                   SELECT types.name, types.subname FROM bufer_to_types, types
                   WHERE bufer_to_types.bufer_id = ? AND types.id = bufer_to_types.types_id;
                   """,
            (result[0],),
        )

    names = []
    types = ""
    for name, submane in cursor.fetchall():
        names.append(name)
        types.append("{name}/{submane}")

    if "text" in names:
         data = binary_data.decode("utf-8").replace("\n", "").replace("\t", "󰌒")
    # elif "image" in names:
        # data = generate_escape_code(binary_data)
    else:
        data = names.__str__() + datetime.datetime.fromtimestamp(date_time).isoformat(" ")
    output = format.format(
            id=indificator, data=data, date_time=date_time, types=types.__str__()
        ).encode("utf-8")


@main.command()
@click.option(
    "-f",
    "--format",
    "format",
    default="{id}. {data}",
    help="Sets the formatting of each string using python `str.format()`, where the following variables can be used: `id`, `data`, `data_time`, `types'.",
)
@click.option(
    "-s",
    "--slice",
    "slice_c",
    default=[],
    multiple=True,
    help="it looks like python slices of lists",
)
@click.pass_context
def get_list(ctx, format: str | None, slice_c):
    """get list of all items"""
    if format == None:
        format = ctx.obj["config"]["default"]["format list"]
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
    cursor.execute(  # get all
        """--sql
                   SELECT * FROM bufer
                   ORDER BY date_time DESC;"""
    )
    results = cursor.fetchall()
    
    if len(slice_c) == 0:
        pass
    elif len(slice_c) == 1:
        results = results[:slice_c[0]]
    elif len(slice_c) == 2:
        results = results[slice_c[0]:slice_c[1]]
    output: bytes = b""

    for indificator, binary_data, date_time in results:
        cursor.execute(  # get type's names
            """--sql
                   SELECT types.name, types.subname FROM bufer_to_types, types
                   WHERE bufer_to_types.bufer_id = ? AND types.id = bufer_to_types.types_id;
                   """,
            (indificator,),
        )

        names = []
        types = ""
        for name, submane in cursor.fetchall():
            names.append(name)
            types.append("{name}/{submane}")

        if "text" in names:
            data = binary_data.decode("utf-8").replace("\n", "").replace("\t", "󰌒")
        # elif "image" in names:
        # data =
        else:
            data = names.__str__() + datetime.datetime.fromtimestamp(
                date_time
            ).isoformat(" ")
        output = format.format(
            id=indificator, data=data, date_time=date_time, types=types.__str__()
        ).encode("utf-8")
    sys.stdout.buffer.write(output)



@main.command()
@click.pass_context
def remove(ctx):
    """remove by id"""
    connection = ctx.obj["connection"]
    cursor = ctx.obj["cursor"]
    index = int(sys.stdin.buffer.read().decode("utf-8").split(".")[0])
    cursor.execute(
        """--sql
                   SELECT COUNT(*) FROM bufer
                   WHERE id = ?;
                   """,
        (index,),
    )
    print(f"Removed {cursor.fetchall()[0]} items.")
    cursor.execute(
        """--sql
                   DELETE FROM bufer
                   WHERE id = ?;
                   """,
        (index,),
    )
    connection.commit()


if __name__ == "__main__":
    main(obj={})

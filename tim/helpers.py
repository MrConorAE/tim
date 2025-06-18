from enum import Enum
import os
from pathlib import Path
from rich import print, panel
import typer
import datetime

v = False


class Range(str, Enum):
    today = "today"
    week = "week"
    month = "month"
    year = "year"
    all = "all"


class Amendables(str, Enum):
    start = "start"
    end = "end"
    tags = "tags"


def set_verbose(verbose: bool):
    global v
    v = verbose


def get_db_path() -> str:
    data_dir = os.getenv("XDG_DATA_HOME", "")
    # If the value of the environment variable is unset, empty, or not an absolute path, use the default
    if data_dir == "" or data_dir[0] != "/":
        return str(Path.home().joinpath(".local", "share", "tim", "data.db"))
    # The value of the environment variable is valid; use it
    return str(Path(data_dir).joinpath("tim", "data.db"))


def create_db_directory(path: str):
    try:
        Path(path).parent.mkdir(parents=True)
        vprint("path: database path created")
    except FileExistsError:
        vprint("path: database path exists")


def get_config_path() -> str:
    return str(Path(typer.get_app_dir("tim")).joinpath("config.toml"))


def vprint(message: str):
    """Print verbose logging. Only prints if verbose mode is on (e.g. for debugging)."""
    if v:
        print("[magenta italic]V: " + message + "[/magenta italic]")


def print_error(message: str, title: str):
    """Create a Panel (from Rich) with sensible options."""
    print(panel.Panel(message, title=title, title_align="left", border_style="red"))


def timestamp(timestamp: int) -> datetime.datetime:
    """Take a Unix timestamp from the database and output a datetime."""
    return datetime.datetime.fromtimestamp(timestamp)


def timestamp_to_absolute(timestamp: int) -> str:
    """Take a Unix timestamp from the database and output an absolute timestamp."""
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def timestamp_to_relative(timestamp: int) -> str:
    """Take a Unix timestamp from the database and output a relative time."""
    relative = datetime.timedelta(seconds=timestamp)
    days = relative.days
    hours = relative.seconds // 3600
    minutes = relative.seconds % 3600 // 60
    seconds = relative.seconds % 60
    string = ""
    if days:
        string += f"{days}d"

    if hours or days:
        string += f"{hours:02}h" if days else f"{hours}h"

    if minutes or hours or days:
        string += f"{minutes:02}m" if days or hours else f"{minutes}m"

    if seconds or minutes or hours or days:
        string += f"{seconds:02}s" if days or hours or minutes else f"{seconds}s"
        
    if not string:
        string += "zero"
        
    # string += f"{days}d" if days else ""
    # string += f"{hours:02}h" if days or hours else ""
    # string += f"{minutes:02}m" if days or hours or minutes else ""
    # string += f"{seconds:02}s" if days or hours or minutes or seconds else "zero"
    
    return string

import sqlite3
import datetime

import tomllib
import typer
from rich.console import Console
from typing_extensions import Annotated, List, Optional

from . import data
from . import helpers as h

app = typer.Typer()
state = {
    "config_file": None,
    "db_file": None,
    "track_amend": False,
    "rate": 0,
    "tag_rate": {},
    "allow_no_tags": True,
    "always_decimal": False,
    "billed_flag": True,
}

console = Console(highlight=False)
print = console.print

DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"]
DATETIME_FORMATS = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"]


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    conf: Annotated[
        str, typer.Option(help="config file location")
    ] = h.get_config_path(),
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="verbose mode - shows more internal details. useful for debugging",
            show_default=False,
        ),
    ] = False,
):
    global state
    """
    tim: a friendly time tracker
    """
    # This function contains global stuff, like loading config files
    # and figuring out where the database is.
    state["config_file"] = conf
    state["db_file"] = h.get_db_path()

    h.set_verbose(verbose)

    h.vprint(f"init: config file is {state['config_file']}")

    try:
        with open(state["config_file"], "rb") as c:
            # load options from the config file
            config = tomllib.load(c)
            h.vprint(f"init: config loaded: {config}")
            if "database" in config:
                state["db_file"] = str(config["database"])
            if "tracking" in config:
                if "track_amend" in config["tracking"]:
                    state["track_amend"] = bool(config["tracking"]["track_amend"])
                if "allow_no_tags" in config["tracking"]:
                    state["allow_no_tags"] = bool(config["tracking"]["allow_no_tags"])
            if "display" in config:
                if "always_decimal" in config["display"]:
                    state["always_decimal"] = bool(config["display"]["always_decimal"])
                if "billed_flag" in config["display"]:
                    state["billed_flag"] = bool(config["display"]["billed_flag"])
    except FileNotFoundError:
        # no config. use defaults.
        h.vprint("init: no config file found. using defaults.")
    except IOError or tomllib.TOMLDecodeError or ValueError or TypeError as e:
        # config exists, but can't read it.
        # rather than continue without the user's preferences being respected,
        # exit and warn about the broken config
        h.vprint(f"init: config file load failed! error: {e}")
        if state["verbose"]:
            h.print_error(
                f"failed to read your config at {state['conf_file']}!\nsee the error information above for more details",
                "failed to read config!",
            )
        else:
            h.print_error(
                f"failed to read your config at {state['conf_file']}!\ntry using [bold]--verbose[/bold] for more information",
                "failed to read config!",
            )
        raise typer.Exit(code=2)

    h.vprint(f"init: database file is {state['db_file']}")

    try:
        data.init(state["db_file"])
    except sqlite3.OperationalError as e:
        h.print_error(
            f"failed to connect to database at {state['db_file']}!\nerror: {e}\nplease check the file exists and is accessible",
            "database error",
        )
        raise typer.Exit(code=3)

    if ctx.invoked_subcommand is None:
        status()


@app.command()
def start(
    replace: Annotated[
        bool,
        typer.Option(
            "--replace",
            "-r",
            help="don't error when already tracking - stops the old tracking and starts the new one automatically.",
            show_default=False,
        ),
    ] = False,
    tags: Annotated[
        Optional[List[str]],
        typer.Argument(help="the tags for this time", show_default="no tags"),
    ] = None,
):
    """
    start tracking time with tags

    returns an error if tracking is already running, unless '--replace' is passed.
    if config option 'allow_no_tags' is false (default true), tags must be provided.
    """
    working = data.check_if_working()
    if not working or (working and replace):
        h.vprint(f"start: got tags {tags} -> '{" ".join(tags) if tags else ''}'")
        if tags is not None and tags != [""]:
            if working:
                stop()
            data.start_work(" ".join(tags))
        elif state["allow_no_tags"]:
            if working:
                stop()
            data.start_work("")
        else:
            h.print_error(
                "not starting - no tags provided, and you have disallowed empty tags",
                "no tags",
            )
            raise typer.Exit(code=1)
        print("[bold green]✓ ok, started tracking!")
        start, duration, db_tags = data.get_current_tracking()
        if db_tags:
            print(f"  working on  {db_tags}")
        else:
            print("  working on  [yellow](no tags)[/yellow]")
        print(f"       since  {h.timestamp_to_absolute(start)}")
        print(f"         for  {h.timestamp_to_relative(duration)}")
    else:
        h.print_error(
            "not starting - you're currently working on something else!\nuse 'tim stop' to stop the current tracking first, or pass '--replace'",
            "currently working",
        )
        start, duration, db_tags = data.get_current_tracking()
        if db_tags:
            print(f"  working on  {db_tags}")
        else:
            print("  working on  [yellow](no tags)[/yellow]")
        print(f"       since  {h.timestamp_to_absolute(start)}")
        print(f"         for  {h.timestamp_to_relative(duration)}")
        raise typer.Exit(code=1)


@app.command("continue")
def continue_work(
    raw_id: Annotated[
        int,
        typer.Argument(
            help="the id of the work to amend. use 0 for the most recent complete log",
            show_default=False,
        ),
    ] = 0,
    replace: Annotated[
        bool,
        typer.Option(
            "--replace",
            "-r",
            help="don't error when already tracking - stops the old tracking and starts the new one automatically.",
            show_default=False,
        ),
    ] = False,
):
    """
    continue tracking, repeating the last (or given) worklog

    returns an error if tracking is already running, unless '--replace' is passed.
    if config option 'allow_no_tags' is false (default true), and last tracking was empty, returns an error.
    """
    id = data.test_id_exists(raw_id)
    if not id:
        h.print_error(
            f"no work record with id {raw_id}.\nuse 'tim log' to see ids", "id not found"
        )
        raise typer.Exit(code=1)
    _, _, _, tags, _ = data.get_tracking(id)
    start(replace, tags.split(" "))


@app.command()
def stop():
    """
    stop tracking

    returns an error if no tracking is running.
    """
    working = data.check_if_working()
    if working:
        data.stop_work()
        print("[bold green]✓ ok, stopped tracking.")
        print("work summary:")
        start, end, duration, tags, _ = data.get_last_tracking()
        if tags:
            print(f"   worked on  {tags}")
        else:
            print("   worked on  [yellow](no tags)[/yellow]")
        print(f"        from  {h.timestamp_to_absolute(start)}")
        print(f"       until  {h.timestamp_to_absolute(end)}")
        print(f"         for  {h.timestamp_to_relative(duration)}")
    else:
        h.print_error("nothing to stop - you're not tracking anything", "not tracking")
        raise typer.Exit(code=1)


@app.command()
def status(    
    terse: Annotated[
        bool,
        typer.Option(
            "--terse",
            "-t",
            help="show a one-line short summary. good for passive monitoring",
        ),
    ] = False,
):
    """
    see the status of your tracking
    """
    working = data.check_if_working()
    if not terse:
        if working:
            print("tim is [bold green]⯈ tracking[/bold green].")
            start, duration, tags = data.get_current_tracking()
            if tags:
                print(f"  working on  {tags}")
            else:
                print("  working on  [yellow](no tags)[/yellow]")
            print(f"       since  {h.timestamp_to_absolute(start)}")
            print(f"         for  {h.timestamp_to_relative(duration)}")
        else:
            print("tim is [bold red]⯀ not tracking[/bold red].")
    else:
        if working:
            start, duration, tags = data.get_current_tracking()
            print(f"tim [bold green]⯈[/bold green] {tags if tags else '[yellow](no tags)[/yellow]'} {h.timestamp_to_relative(duration)}")
        else:
            print("tim [bold red]⯀ not tracking[/bold red]")
        


@app.command()
def log(
    filter: Annotated[
        Optional[List[str]],
        typer.Argument(
            help="tags to filter for",
            show_default="show all",
        ),
    ] = None,
    partial: Annotated[
        bool,
        typer.Option(
            "--partial",
            "-p",
            help="don't require whole tag matches for filtering (wildcard mode)",
            rich_help_panel="search",
        ),
    ] = False,
    range: Annotated[
        h.Range,
        typer.Option(
            "--range",
            "-r",
            help="the range to view",
            rich_help_panel="search",
        ),
    ] = h.Range.week,
    billed: Annotated[
        Optional[bool],
        typer.Option(
            "--billed/--unbilled",
            "-B/-b",
            help="show billed or unbilled only",
            show_default="all",
            rich_help_panel="search",
        ),
    ] = None,
    decimal: Annotated[
        bool,
        typer.Option(
            "--decimal",
            "-d",
            help="show durations in decimal hours instead of hours, minutes, seconds",
            rich_help_panel="display",
        ),
    ] = False,
    long: Annotated[
        bool,
        typer.Option(
            "--long",
            "-l",
            help="show every detail about tracked work",
            rich_help_panel="display",
        ),
    ] = False,
    rate: Annotated[
        Optional[float],
        typer.Option(
            "--rate",
            "-a",
            help="your working rate. if provided, an amount will be shown in the summary",
            rich_help_panel="display",
        ),
    ] = None,
):
    """
    see your work history
    """
    log = data.get_work_log(range, billed, filter, partial)

    if range == h.Range.today:
        print("your log for [bold]today[/bold]")
    elif range == h.Range.all:
        print("your log for [bold]all time[/bold]")
    else:
        print(f"your log for [bold]the last {range.name}[/bold]")

    if filter:
        print(
            f"  showing only work with tags '{" ".join(filter)}'{' (partial matching)' if partial else ''}"
        )

    if billed is not None:
        if billed:
            print("  showing only billed work ([green]B[/green])")
        else:
            print("  showing only unbilled work ([yellow]b[/yellow])")

    if rate:
        print(f"  using rate of {rate:.2f}/hr")

    if state["always_decimal"]:
        decimal = True

    if decimal:
        print("  using decimal hours")

    if long:
        print("  showing more details")

    print()

    print(
        f"[bright_black underline]{'id':<5}   {'start':<23}   {'end':<10}   {'duration':<12}   f     {'tags':<19}"
    )

    time_sum_sec = 0
    last_start = 0
    date_rollover_warning = False
    billed_flag = "[green]B[/green]" if state["billed_flag"] else " "

    if len(log) == 0:
        print(
            "[bold]  no tracked work to show![/bold]\n  try a different time range or filter."
        )
    else:
        for id, start_sec, end_sec, duration_sec, tags, bill, amended in log:
            h.vprint(f"{(id, start_sec, end_sec, duration_sec, tags, bill, amended)}")
            start_ts = h.timestamp(start_sec)

            if h.timestamp(last_start).date() != start_ts.date():
                # date has changed
                start = start_ts.strftime("%a %Y-%m-%d %H:%M:%S")
                last_start = start_sec
            else:
                start = start_ts.strftime("               %H:%M:%S")

            flags = f"{"[yellow]b[/yellow]" if not bill else billed_flag}{"[red]A[/red]" if amended and state['track_amend'] else " "}{"[bright_green]⯈[/bright_green]" if end_sec is None else " "}"

            if not tags:
                tags = "[bright_black](no tags)[/bright_black]"

            if end_sec is None:
                _, duration_sec, _ = data.get_current_tracking()
                if decimal:
                    duration = f"{duration_sec/3600:>11.3f}h"
                else:
                    duration = h.timestamp_to_relative(duration_sec)
                print(
                    f"{id:>5}   {start}   [bright_black]{"--  ":>10}[/bright_black]   [bright_green]{duration:>12}[/bright_green]   {flags}   [bold bright_green]{tags}[/bold bright_green]"
                )
            else:
                end_ts = h.timestamp(end_sec)
                if start_ts.date() != end_ts.date():
                    # date has changed (period rolls over a midnight)
                    end = end_ts.strftime("%H:%M:%S [bold red]⬧[/bold red]")
                    date_rollover_warning = True
                else:
                    end = end_ts.strftime("%H:%M:%S  ")

                if decimal:
                    duration = f"{duration_sec/3600:>11.3f}h"
                else:
                    duration = h.timestamp_to_relative(duration_sec)
                print(
                    f"{id:>5}   {start}   {end}   {duration:>12}   {flags}   [bold]{tags}[/bold]"
                )

            if long:
                print(
                    (" " * 70)
                    + f"billed: {f"[green]yes[/green], ref '{bill}'" if bill else "[yellow]no[/yellow]"};  amended: {("[red]yes[/red]" if amended else "no") if state['track_amend'] else "--"}"
                )

            time_sum_sec += duration_sec

    print()
    print(
        f"[bright_black underline]{'':<5}   {'':<23}   {'entries':<10}   {'time' + (' (value)' if rate else ''):<12}"
    )

    if decimal:
        time_sum = f"{time_sum_sec/3600:>11.3f}h"
    else:
        time_sum = h.timestamp_to_relative(time_sum_sec)

    print(f"[bold]{'':>5}   {'':>23}   {len(log):>10}   {time_sum:>12}")

    if rate:
        time_value = round((time_sum_sec / 3600) * rate, 2)
        print(f"[bold]{'':>5}   {'':>23}   {'':>10}   {time_value:>12.2f}")

    print()

    if data.check_if_working():
        print(
            "warning: you are currently tracking work ([bright_green]⯈[/bright_green]) - values are not final\n"
        )
    if date_rollover_warning:
        print("warning: some periods span multiple days ([red]⬧[/red])\n")


@app.command()
def delete(
    id: Annotated[
        int,
        typer.Argument(
            help="the id of the work to delete. use 0 for the most recent complete log"
        ),
    ],
):
    """
    delete recorded work

    no confirmation is given, so be careful!
    """
    success = data.delete_work(id)
    if success:
        print("[bold green]✓ ok, deleted " + ("last work log" if id == 0 else f"work log #{id}") + "[/bold green]")
    else:
        h.print_error(
            f"no work record with id {id}.\nuse 'tim log' to see ids", "id not found"
        )


@app.command()
def bill(
    filter: Annotated[
        Optional[List[str]],
        typer.Argument(help="tags to filter for", show_default="show all"),
    ] = None,
    partial: Annotated[
        bool,
        typer.Option(
            "--partial",
            "-p",
            help="don't require whole tag matches for filtering (wildcard mode)",
            rich_help_panel="filter by tags",
        ),
    ] = False,
    range_from: Annotated[
        Optional[datetime.datetime],
        typer.Option(
            "--from",
            "-f",
            help="start of range to bill",
            show_default="beginning of time",
            formats=DATE_FORMATS,
            rich_help_panel="filter by date",
        ),
    ] = None,
    range_to: Annotated[
        Optional[datetime.datetime],
        typer.Option(
            "--to",
            "-t",
            help="end of range to bill",
            show_default="end of time",
            formats=DATE_FORMATS,
            rich_help_panel="filter by date",
        ),
    ] = None,
    range_all: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="mark all matching work as billed (instead of providing from, to, or tags). dangerous!",
            rich_help_panel="filter by date",
        ),
    ] = False,
    ref: Annotated[
        Optional[str],
        typer.Option(
            "--ref",
            "-r",
            help="bill reference, like an invoice number",
            show_default="no ref",
            rich_help_panel="bill options",
        ),
    ] = None,
    unbill: Annotated[
        bool,
        typer.Option(
            "--unbill",
            help="mark as not billed instead of billed. dangerous!",
            rich_help_panel="bill options",
        ),
    ] = False,
):
    """
    mark work as billed (or not)

    supply one or both of '--from' and '--to' (or '--all'), and optionally tags to filter for. you can also provide a bill reference, like an invoice number, with '--ref'.
    """
    h.vprint(f"range = from {range_from} to {range_to}, all is {range_all}")

    if range_from is None and range_to is None and not range_all:
        h.print_error(
            "specify at least one of '--from' or '--to', or '--all' to use all",
            "no range given",
        )
        raise typer.Exit(code=1)
    if range_all and (range_from is not None or range_to is not None):
        h.print_error(
            "'--from'/'--to' and '--all' are mutually exclusive",
            "from/to used with all",
        )
        raise typer.Exit(code=1)

    if range_all:
        print("ok, marking all work")
    else:
        if range_from and range_to:
            print(
                f"ok, marking work\n  between {range_from.date()} and {range_to.date()}"
            )
        elif range_from:
            print(f"ok, marking work\n  from {range_from.date()}")
        elif range_to:
            print(f"ok, marking work\n  to {range_to.date()}")

    if filter:
        print(
            f"  with tags '{" ".join(filter)}'{' (partial matching)' if partial else ''}"
        )

    if unbill:
        print("  as [yellow]not billed[/yellow]")
    else:
        print("  as [green]billed[/green]")

    data.mark_work_billed(range_from, range_to, range_all, filter, partial, ref, unbill)


@app.command()
def amend(
    raw_id: Annotated[
        int,
        typer.Argument(
            help="the id of the work to amend. use 0 for the most recent complete log",
            show_default=False,
        ),
    ],
    attribute: Annotated[
        h.Amendables,
        typer.Argument(
            help="what to amend",
            show_default=False,
        ),
    ],
    new_time: Annotated[
        Optional[datetime.datetime],
        typer.Option(
            "--time",
            "-t",
            help="new timestamp to apply",
            show_default=False,
            formats=DATETIME_FORMATS,
        ),
    ] = None,
    new_tags: Annotated[
        Optional[List[str]],
        typer.Option("--tags", "-a", help="new tags to apply", show_default=False),
    ] = None,
    billed_ack: Annotated[
        bool,
        typer.Option(
            "--modify-billed",
            help="allow modifying times on billed items (disallowed by default)",
            show_default=False,
        ),
    ] = False,
):
    """
    amend tracked work

    change start or stop times, or modify tags for a work period. use 0 for last complete work.
    if amend tracking is enabled in your config (off by default), amended work will be flagged in the log.
    """
    h.vprint(f"amending {attribute} of id {raw_id}")
    id = data.test_id_exists(raw_id)
    if not id:
        h.print_error(
            f"no work record with id {raw_id}.\nuse 'tim log' to see ids", "id not found"
        )
        raise typer.Exit(code=1)

    if attribute == h.Amendables.tags:
        if new_tags is not None and new_tags != [""]:
            data.amend_tags(id, " ".join(new_tags))
        elif state["allow_no_tags"]:
            data.amend_tags(id, "")
        else:
            h.print_error(
                "no tags provided, and you have disallowed empty tags",
                "no tags",
            )
            raise typer.Exit(code=1)
    elif attribute == h.Amendables.start or attribute == h.Amendables.end:
        # check if it's been billed
        _, _, _, _, bill = data.get_tracking(id)
        if bill and not billed_ack:
            h.print_error(
                "warning: this work has already been billed. modifying timestamps would cause the " +
                "bill to change amount.\nif you really want to do this, try again with '--modify-billed'.",
            "already billed"
            )
            raise typer.Exit(code=2)
        if new_time is None:
            h.print_error(
                "provide a new time value with --time", "no time"
            )
            raise typer.Exit(code=1)
        data.amend_time(id, attribute.value, new_time)

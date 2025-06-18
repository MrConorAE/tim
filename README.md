# `tim`
## a friendly uncomplicated time tracker

I wrote this because I couldn't find a simple, CLI-based time tracker that also supported marking work as 'billed' or not, which was important to me for the projects I was working on - so I hacked together `tim` in a weekend.

I eventually figured that someone else might find this useful, so now it's on GitHub! Feel free to make issues or (better still) PRs :)

More documentation to come... just as soon as I write it.

**Usage**:

```console
$ tim [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--conf TEXT`: config file location  [default: /home/conor/.config/tim/config.toml]
* `-v, --verbose`: verbose mode - shows more internal details. useful for debugging
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `start`: start tracking time with tags
* `continue`: continue tracking, repeating the last tags
* `stop`: stop tracking
* `status`: see the status of your tracking
* `log`: see your work history
* `delete`: delete recorded work
* `bill`: mark work as billed (or not)
* `amend`: amend tracked work

## `tim start`

start tracking time with tags

returns an error if tracking is already running, unless &#x27;--replace&#x27; is passed.
if config option &#x27;allow_no_tags&#x27; is false (default true), tags must be provided.

**Usage**:

```console
$ tim start [OPTIONS] [TAGS]...
```

**Arguments**:

* `[TAGS]...`: the tags for this time  [default: (no tags)]

**Options**:

* `-r, --replace`: don&#x27;t error when already tracking - stops the old tracking and starts the new one automatically.
* `--help`: Show this message and exit.

## `tim continue`

continue tracking, repeating the last tags

returns an error if tracking is already running, unless &#x27;--replace&#x27; is passed.
if config option &#x27;allow_no_tags&#x27; is false (default true), and last tracking was empty, returns an error.

**Usage**:

```console
$ tim continue [OPTIONS]
```

**Options**:

* `-r, --replace`: don&#x27;t error when already tracking - stops the old tracking and starts the new one automatically.
* `--help`: Show this message and exit.

## `tim stop`

stop tracking

returns an error if no tracking is running.

**Usage**:

```console
$ tim stop [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `tim status`

see the status of your tracking

**Usage**:

```console
$ tim status [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `tim log`

see your work history

**Usage**:

```console
$ tim log [OPTIONS] [FILTER]...
```

**Arguments**:

* `[FILTER]...`: tags to filter for  [default: (show all)]

**Options**:

* `-p, --partial`: don&#x27;t require whole tag matches for filtering (wildcard mode)
* `-r, --range [today|week|month|year|all]`: the range to view  [default: week]
* `-B, --billed / -b, --unbilled`: show billed or unbilled only  [default: (all)]
* `-d, --decimal`: show durations in decimal hours instead of hours, minutes, seconds
* `-l, --long`: show every detail about tracked work
* `-a, --rate FLOAT`: your working rate. if provided, an amount will be shown in the summary
* `--help`: Show this message and exit.

## `tim delete`

delete recorded work

no confirmation is given, so be careful!

**Usage**:

```console
$ tim delete [OPTIONS] ID
```

**Arguments**:

* `ID`: the id of the work to delete. use 0 for the most recent complete log  [required]

**Options**:

* `--help`: Show this message and exit.

## `tim bill`

mark work as billed (or not)

supply one or both of &#x27;--from&#x27; and &#x27;--to&#x27; (or &#x27;--all&#x27;), and optionally tags to filter for. you can also provide a bill reference, like an invoice number, with &#x27;--ref&#x27;.

**Usage**:

```console
$ tim bill [OPTIONS] [FILTER]...
```

**Arguments**:

* `[FILTER]...`: tags to filter for  [default: (show all)]

**Options**:

* `-p, --partial`: don&#x27;t require whole tag matches for filtering (wildcard mode)
* `-f, --from [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%dT%H:%M]`: start of range to bill  [default: (beginning of time)]
* `-t, --to [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%dT%H:%M]`: end of range to bill  [default: (end of time)]
* `-a, --all`: mark all matching work as billed (instead of providing from, to, or tags). dangerous!
* `-r, --ref TEXT`: bill reference, like an invoice number  [default: (no ref)]
* `--unbill`: mark as not billed instead of billed. dangerous!
* `--help`: Show this message and exit.

## `tim amend`

amend tracked work

change start or stop times, or modify tags for a work period. use 0 for last complete work.
if amend tracking is enabled in your config (off by default), amended work will be flagged in the log.

**Usage**:

```console
$ tim amend [OPTIONS] RAW_ID ATTRIBUTE:{start|end|tags}
```

**Arguments**:

* `RAW_ID`: the id of the work to amend. use 0 for the most recent complete log  [required]
* `ATTRIBUTE:{start|end|tags}`: what to amend  [required]

**Options**:

* `-t, --time [%Y-%m-%dT%H:%M:%S|%Y-%m-%dT%H:%M]`: new timestamp to apply
* `-a, --tags TEXT`: new tags to apply
* `--modify-billed`: allow modifying times on billed items (disallowed by default)
* `--help`: Show this message and exit.

# Dismob Logs Plugin

This is a [dismob](https://github.com/dismob/dismob) plugin which logs actions of the members.
They can be activated/deactivated individually and dispatched in multiple channels for organizing your logs.

## Installation

> [!IMPORTANT]
> You need to have an already setup [dismob](https://github.com/dismob/dismob) bot. Follow the instruction there to do it first.

Just download/clone (or add as submodule) this repo into your dismob's `plugins` folder.  
The path **must** be `YourBot/plugins/logs/main.py` at the end.

Once your bot is up and live, run those commands on your discord server:

```
!modules load logs
!sync
```

> [!NOTE]
> Replace the prefix `!` by your own bot prefix when doing those commands!

Then you can reload your discord client with `Ctrl+R` to see the new slash commands.

## Commands

Command | Description
--- | ---
`/warn <member> <reason>` | Warn a member.

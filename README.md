## Dynashell

A flexible shell to run Python snippets in a configurable context

### Description

Dynashell is a small compact module that can be used to run Python code in a configurable context.
It includes a simple command prompt that lets the user execute Python scripts within a running python context.

Users can edit their scripts and rerun them without the need to stop/start the shell. This is useful when the context
contains connections to other systems (like Spark or a database) that might take time to establish.

Users can add their own modules to the shell context and have common code included in each script that
is executed.

Dynashell parses the line entered on the command prompt and makes it available to the script that
gets executed from it.

For more detailed information about the workings of dynashell go to the [documentation](./doc/README.md).





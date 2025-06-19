# Dynashell Examples

To run these example, you need to invoke the dynashell in the following way :

    python -m dynashell.main --config=./<example>/config.yaml

Make sure the dynashell module can be found by python. On linux you can add the src path
to the PYTHONPATH as follows :

    export PYTHONPATH=`pwd`/../src

## Simple example

Start the simple example as described above. Once you see the '>' prompt, type the following :

    >show_config

This will execute the command stored under ./example/simple/script/show_config. It will simple print
the exported variable 'config'

Next, execute the connect command :

    >connect dev

This will execute the command stored under ./example/common/script/connect. It will get the 'dev' argument
from the command line and uses it to retrieve the connection data for dev under config.connect.dev.
It then calls the connect() function. The connect function was imported automatically because it was defined
by the 'include' section in config.yaml.




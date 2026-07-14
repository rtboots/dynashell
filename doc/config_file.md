[[main](README.md)] 

### Config File

When the Dynashell instance is created, it will need a configuration YAML file. You can specify the file
to be read on the startup line :

```commandline
dynashell <arguments> --config=<file>
```
If no configuration file is specified it will look for a file called **config.yaml** in the current directory.

The configuration file can contain the following system sections :

| section  | purpose                                                            |
|----------|--------------------------------------------------------------------|
| path     | Define additional path prefixes (see [paths](path_prefixes.md))         |
| module   | Define paths for resolving module **import** statements in scripts |
| source   | Define paths for script resolution                                 |
| include  | Define common script header                                        |
| startup  | Define scripts to be run on shell startup                          |
| shutdown | Define scripts to be run on shell shutdown                         |
| feature  | Enable optional script features                                    |

Additional sections can be added to the configuration and will be considered context specific and
won't be processed.

Scripts can access the configuration by accessing the declared **config** variable.

```
config.path
```
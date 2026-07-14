[[main](README.md)] 

### Paths

Dynashell uses prefixes in path specifications for simplification. On startup of dynashell
2 prefixes are already defined :

| prefix      | value                                             |
|-------------|---------------------------------------------------|
| **system:** | The directory dynashell is started in             |
| **shell:**  | The directory the configuration file is read from |

The configuration file has a *path* section that allows for additional prefixes to be specified 
(see [config](config.md)).

Some prefixes are implicitly defined if they have not been defined in the configuration :

| prefix    | value       |
|-----------|-------------|
| **temp:** | shell:/temp |

When dynashell needs to perform file or path operations, it will inspect the file or path string
to see if it starts with a registered prefix and replaces the prefix with its defined value.  

if **shell:** is defied as "/home/john/runme" then **shell:/temp** will resolve in "/home/john/runme/temp".

hg-extensions
=============

A collection of hg extensions bringing some added value to my workflow

## webrev
Allows to create and upload OpenJDK webrev based either on a specific revision, feature branch or an MQ patch.

### Usage
`hg webrev [options]`

#### Options
* *-u, --update* - will not generate the new sequnce suffix for the webrev and update the latest one instead
* *-r, --revision* - the revision to create the webrev for
* *-i, --issue* - the associated issue
* *--server* - the webrev upload server
 
### Configuration
All the configuration is done in the _hgrc_ file

#### Enabling Extension
```
[extensions]
...
webrev = <path to webrev.py>
...
```

#### Configuring JBS access
```
[jbs]
username = <user name>
password = <password>
```

hg-extensions
=============

A collection of hg extensions bringing some added value to my workflow

## webrev
Allows to create and upload OpenJDK webrev based either on a specific revision, feature branch or an MQ patch.

### Usage
`hg webrev [options]`

The JDK issue number is inferred from either the MQ patch name, the branch name or the bookmark name. If any of those values start with 'JDK-' they are considered as the issue link.

When the issue number can not be inferred a prompt is presented where you can enter the issue number manually.

#### Options
* *-u, --update* - will not generate the new sequnce suffix for the webrev and update the latest one instead
* *-c, --category* - an additional qualifier eg. 'jdk'; useful for putting eg. hotspot + jdk changes under one review
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

#### Configuring e-mail generator

By setting up the mail generator properly the extension will create a templated review request

```
[webrev]
# the mailing application
# $subject and $body will get replaced by the actual values
mailer = thunderbird -compose subject=$subject,body=$body
```

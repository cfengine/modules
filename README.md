# CFEngine modules

This repository contains reusable modules, made by the CFEngine team and officially supported.

## Promise types

Modules which allow you to add new promise types to CFEngine policy language, making it easier to manage these resources:

* [Git](./promise_types/git/)
* [Groups (experimental)](./promise_types/groups-experimental)

## Promise type libraries

Most custom promise types depend on one of these libraries:

* [Python library](./libraries/python/)
* [Bash library](./libraries/bash/)

## Examples

These are not ready to use, but rather used for educational purposes, as examples in tutorials, documentation, and blog post:

* [Backup custom promise type](./promise_types/backup/)
* [Copy file custom promise type](./promise_types/cp/)
* [Git promise type written from scratch](./promise_types/git-from-scratch/)
* [Git promise type written using library](./promise_types/git-using-lib/)
* [GPG key custom promise type](./promise_types/gpg/)
* [Site status custom promise type](./promise_types/site-up/)

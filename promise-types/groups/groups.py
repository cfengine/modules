import re
import json
from subprocess import Popen, PIPE
from cfengine import PromiseModule, ValidationError, Result


class GroupsPromiseTypeModule(PromiseModule):
    def __init__(self):
        super().__init__("groups_promise_module", "0.2.4")
        self._name_regex = re.compile(r"^[a-z_][a-z0-9_-]*[$]?$")
        self._name_maxlen = 32

    def validate_promise(self, promiser, attributes, metadata):
        # check promiser value
        if self._name_regex.match(promiser) is None:
            self.log_warning(
                "Promiser groupname '%s' should match regular expression '[a-z_][a-z0-9_-]*[$]?'"
                % promiser
            )

        # check promiser length not too long
        if len(promiser) > self._name_maxlen:
            raise ValidationError(
                "Promiser '%s' is too long: (%d > %d)"
                % (promiser, len(promiser), self._name_maxlen)
            )

        # check attribute policy if present
        if "policy" in attributes:
            policy = attributes["policy"]

            # check attribute policy type
            if type(policy) is not str:
                raise ValidationError(
                    "Invalid type for attribute policy: expected string"
                )

            # check attribute policy value
            if policy not in ("present", "absent"):
                raise ValidationError(
                    "Invalid value '%s' for attribute policy: must be 'present' or 'absent'"
                    % policy
                )

            # check attributes gid and members are not used with policy absent
            if policy == "absent":
                if "gid" in attributes:
                    self.log_warning(
                        "Cannot assign gid to absent group '%s'" % promiser
                    )
                if "members" in attributes:
                    self.log_warning(
                        "Cannot assign members to absent group '%s'" % promiser
                    )

        # check attribute gid if present
        if "gid" in attributes:
            gid = attributes["gid"]

            # check attribute gid type
            if type(gid) not in (str, int):
                raise ValidationError(
                    "Invalid type for attribute gid: expected string or int"
                )

            # check attribute gid value
            if type(gid) == str:
                try:
                    int(gid)
                except ValueError:
                    raise ValidationError(
                        "Invalid value '%s' for attribute gid: expected integer literal"
                        % gid
                    )

        # check attribute members if present
        if "members" in attributes:
            # Parse as JSON, if type is string
            if type(attributes["members"]) is str:
                try:
                    attributes["members"] = json.loads(attributes["members"])
                except json.JSONDecodeError:
                    raise ValidationError(
                        "Invalid value for attribute 'members': Could not parse JSON"
                    )
            # Type should be dict if custom body or data container is used instead
            elif type(attributes["members"]) is not dict:
                raise ValidationError(
                    "Invalid type for attribute 'members': expected 'body', 'data' or 'string'"
                )
            members = attributes["members"]

            # check attribute only not used with attributes include or exclude
            if "only" in members and ("include" in members or "exclude" in members):
                raise ValidationError(
                    "Attribute 'only' may not be used with attributes 'include' or 'exclude'"
                )

            # check attributes of attibutes in members
            for attr in members:
                if attr not in ("only", "include", "exclude"):
                    raise ValidationError(
                        "Invalid value '%s' in attribute members: must be 'only', 'exclude' or 'include'"
                        % attr
                    )

            # make sure users aren't both included and excluded
            if "include" in members and "exclude" in members:
                duplicates = set(members["include"]).intersection(
                    set(members["exclude"])
                )
                if duplicates != set():
                    raise ValidationError(
                        "Users %s both included and excluded from group '%s'"
                        % (duplicates, promiser)
                    )

    def evaluate_promise(self, promiser, attributes, metadata):
        # keep track of any repairs or failed repairs
        failed_repairs = 0
        repairs = 0

        # get group from '/etc/group' if present
        group = None
        try:
            group = Group.lookup(promiser)
        except GroupException as e:
            self.log_error("Failed to lookup group '%s': %s" % (promiser, e))
            failed_repairs += 1

        # get promised gid if present
        promised_gid = attributes.get("gid")

        # parse json in attribute members
        if "members" in attributes:
            # if members attribute is passed as a string, parse it as json
            if type(attributes["members"]) is str:
                attributes["members"] = json.loads(attributes["members"])
            else:
                assert type(attributes["members"]) is dict

        # set policy to present by default, if not specified
        if "policy" not in attributes:
            self.log_verbose("Policy not specified, defaults to present")
            attributes["policy"] = "present"

        # create group if policy present and group absent
        if attributes["policy"] == "present" and group is None:
            self.log_debug(
                "Group '%s' should be present, but does not exist" % promiser
            )
            try:
                group = Group.create(promiser, promised_gid)
            except GroupException as e:
                self.log_error("Failed to create group '%s': %s" % (promiser, e))
                failed_repairs += 1
            else:
                self.log_info("Created group '%s'" % promiser)
                repairs += 1

        # delete group if policy absent and group present
        elif attributes["policy"] == "absent" and group is not None:
            self.log_debug("Group '%s' should be absent, but does exist" % promiser)
            try:
                # group is set to None here
                group = group.delete()
            except GroupException as e:
                self.log_error("Failed to delete group '%s': %s" % (promiser, e))
                failed_repairs += 1
            else:
                self.log_info("Deleted group '%s'" % promiser)
                repairs += 1

        # if group is now present, check attributes 'gid' and 'members'
        if group is not None:
            # check gid if present
            if promised_gid is not None and promised_gid != group.gid:
                self.log_error(
                    "There is an existing group '%s' with a different GID (%s) than promised (%s)"
                    % (promiser, group.gid, promised_gid)
                )
                # We will not try to repair this, as this might grant permissions to group
                failed_repairs += 1

            # check members if present
            if "members" in attributes:
                members = attributes["members"]
                set_members_repairs, set_members_failed_repairs = self._set_members(
                    group, members
                )
                repairs += set_members_repairs
                failed_repairs += set_members_failed_repairs

        self.log_debug(
            "'%s' repairs and '%s' failed repairs to promiser '%s'"
            % (repairs, failed_repairs, promiser)
        )
        if failed_repairs > 0:
            self.log_error("Promise '%s' not kept" % promiser)
            return Result.NOT_KEPT

        if repairs > 0:
            self.log_verbose("Promise '%s' repaired" % promiser)
            return Result.REPAIRED

        self.log_verbose("Promise '%s' kept" % promiser)
        return Result.KEPT

    def _set_members(self, group, members):
        repairs = 0
        failed_repairs = 0

        for attribute in members:
            if attribute == "include":
                users = members["include"]
                (
                    include_users_repairs,
                    include_users_failed_repairs,
                ) = self._include_users(group, users)
                repairs += include_users_repairs
                failed_repairs += include_users_failed_repairs

            elif attribute == "exclude":
                users = members["exclude"]
                (
                    exclude_users_repairs,
                    exclude_users_failed_repairs,
                ) = self._exclude_users(group, users)
                repairs += exclude_users_repairs
                failed_repairs += exclude_users_failed_repairs

            elif attribute == "only":
                users = members["only"]
                only_users_repairs, only_users_failed_repairs = self._only_users(
                    group, users
                )
                repairs += only_users_repairs
                failed_repairs += only_users_failed_repairs

        return repairs, failed_repairs

    def _include_users(self, group, users):
        repairs = 0
        failed_repairs = 0

        for user in users:
            self.log_debug(
                "User '%s' should be included in group '%s'" % (user, group.name)
            )
            if user in group.members:
                self.log_debug(
                    "User '%s' already included in group '%s'" % (user, group.name)
                )
            else:
                self.log_debug(
                    "User '%s' not included in group '%s'" % (user, group.name)
                )
                try:
                    group.add_member(user)
                except GroupException as e:
                    self.log_error(
                        "Failed to add user '%s' to group '%s': %s"
                        % (user, group.name, e)
                    )
                    failed_repairs += 1
                else:
                    self.log_info("Added user '%s' to group '%s'" % (user, group.name))
                    repairs += 1

        return repairs, failed_repairs

    def _exclude_users(self, group, users):
        repairs = 0
        failed_repairs = 0

        for user in users:
            self.log_debug(
                "User '%s' should be excluded from group '%s'" % (user, group.name)
            )
            if user in group.members:
                self.log_debug(
                    "User '%s' not excluded from group '%s'" % (user, group.name)
                )
                try:
                    group.remove_member(user)
                except GroupException as e:
                    self.log_error(
                        "Failed to remove user '%s' from group '%s': %s"
                        % (user, group.name, e)
                    )
                    failed_repairs += 1
                else:
                    self.log_info(
                        "Removed user '%s' from group '%s'" % (user, group.name)
                    )
                    repairs += 1
            else:
                self.log_debug(
                    "User '%s' already excluded from group '%s'" % (user, group.name)
                )

        return repairs, failed_repairs

    def _only_users(self, group, users):
        repairs = 0
        failed_repairs = 0

        self.log_debug(
            "Group '%s' should only contain members %s" % (group.name, users)
        )
        if set(users) != set(group.members):
            self.log_debug(
                "Group '%s' does not only contain members %s" % (group.name, users)
            )
            try:
                group.set_members(users)
            except GroupException as e:
                self.log_error(
                    "Failed to set members of group '%s' to only users %s: %s"
                    % (group.name, users, e)
                )
                failed_repairs += 1
            else:
                self.log_info(
                    "Members of group '%s' set to only users %s" % (group.name, users)
                )
                repairs += 1
        else:
            self.log_debug(
                "Group '%s' does only contain members %s" % (group.name, users)
            )

        return repairs, failed_repairs


class GroupException(Exception):
    def __init__(self, message):
        self.message = message


class Group:
    def __init__(self, name, gid, members):
        self.name = name
        self.gid = gid
        self.members = members

    @staticmethod
    def lookup(group):
        try:
            with open("/etc/group") as f:
                for line in f:
                    if line.startswith(group + ":"):
                        entry = line.strip().split(":")
                        name = entry[0]
                        gid = entry[2]
                        members = entry[3].split(",") if entry[3] else []
                        return Group(name, gid, members)
        except Exception as e:
            raise GroupException(e)
        return None

    @staticmethod
    def create(name, gid=None):
        command = ["groupadd", name]
        if gid:
            command += ["--gid", gid]
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        _, stderr = process.communicate()

        if process.returncode != 0:
            # we'll only use the first line of stderr output,
            # as remaining lines dwell into too much detail
            msg = stderr.decode("utf-8").strip().split("\n")[0]
            raise GroupException(msg)

        return Group.lookup(name)

    def delete(self):
        command = ["groupdel", self.name]
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        _, stderr = process.communicate()

        if process.returncode != 0:
            # we'll only use the first line of stderr output,
            # as remaining lines dwell into too much detail
            msg = stderr.decode("utf-8").strip().split("\n")[0]
            raise GroupException(msg)

        return None

    def add_member(self, user):
        command = ["gpasswd", "--add", user, self.name]
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        _, stderr = process.communicate()

        if process.returncode != 0:
            # we'll only use the first line of stderr output,
            # as remaining lines dwell into too much detail
            msg = stderr.decode("utf-8").strip().split("\n")[0]
            raise GroupException(msg)

    def remove_member(self, user):
        command = ["gpasswd", "--delete", user, self.name]
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        _, stderr = process.communicate()

        if process.returncode != 0:
            # we'll only use the first line of stderr output,
            # as remaining lines dwell into too much detail
            msg = stderr.decode("utf-8").strip().split("\n")[0]
            raise GroupException(msg)

    def set_members(self, users):
        command = ["gpasswd", "--members", ",".join(users), self.name]
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        _, stderr = process.communicate()

        if process.returncode != 0:
            # we'll only use the first line of stderr output,
            # as remaining lines may dwell into too much detail
            msg = stderr.decode("utf-8").strip().split("\n")[0]
            raise GroupException(msg)


if __name__ == "__main__":
    GroupsPromiseTypeModule().start()

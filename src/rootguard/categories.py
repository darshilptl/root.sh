"""Deterministic shell-command classification.

This module never executes a command. It parses the command text with
``shlex`` where possible and applies a rule table to derive the four action
properties used by the feature extractor:

* ``action_class`` -- one of the 17 request/action classes;
* ``reversibility`` -- 0 reversible, 1 irreversible;
* ``scope`` -- 0 single file/process, 1 folder/multi-file, 2 system-wide;
* ``privilege`` -- 0 user, 1 root.

It also exposes a hard safety floor (:func:`catastrophic_reason`) for
catastrophic command shapes.  The safety floor is deliberately independent of
the learned model: a model error must not make a disk-wiping command runnable.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath

from rootguard.intent import INTENT_CLASSES

ACTION_CLASSES: tuple[str, ...] = tuple(INTENT_CLASSES)

#: Commands whose presence makes the action destructive even when the command
#: is wrapped by ``sudo`` or invoked through a shell script.
DESTRUCTIVE_COMMANDS: frozenset[str] = frozenset(
    {
        "rm",
        "rmdir",
        "unlink",
        "shred",
        "truncate",
        "mkfs",
        "mkfs.ext4",
        "mkfs.xfs",
        "wipefs",
        "fdisk",
        "parted",
        "dd",
        "kill",
        "pkill",
        "killall",
        "shutdown",
        "reboot",
        "poweroff",
        "halt",
    }
)

#: Absolute paths that are system-wide or otherwise privileged.  The trailing
#: slash is intentionally omitted: prefix checks use ``path == p or
#: path.startswith(p + "/")``.
SYSTEM_PREFIXES: tuple[str, ...] = (
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
    "/root",
    "/var/lib",
    "/var/run",
)

#: Paths holding credentials or other secrets.  Reading them is not by itself
#: proof of exfiltration, but combining them with a network/remote sink is.
SENSITIVE_PATHS: tuple[str, ...] = (
    "/etc/shadow",
    "/etc/gshadow",
    "/etc/sudoers",
    "/etc/passwd",
    "/root/.ssh",
    "/.ssh/id_",
    "/.ssh/authorized_keys",
    "/.aws/credentials",
    "/.config/gcloud",
    "/.git-credentials",
    "/.netrc",
    "/.kube/config",
    "/.docker/config.json",
    "/.config/gh/hosts.yml",
)

#: Commands that send data to a remote endpoint.
REMOTE_SINK_COMMANDS: frozenset[str] = frozenset(
    {"scp", "rsync", "ssh", "sftp", "ftp", "nc", "ncat", "netcat", "curl", "wget"}
)

#: Commands that execute downloaded content.
SHELLS: frozenset[str] = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish", "python", "python3", "perl", "ruby", "node"})

_COMMAND_CLASSES: dict[str, str] = {
    # read-only / inspection
    "ls": "list_read",
    "dir": "list_read",
    "cat": "list_read",
    "tac": "list_read",
    "head": "list_read",
    "tail": "list_read",
    "less": "list_read",
    "more": "list_read",
    "most": "list_read",
    "file": "list_read",
    "stat": "list_read",
    "wc": "list_read",
    "tree": "list_read",
    "du": "list_read",
    "df": "list_read",
    "pwd": "list_read",
    "whoami": "list_read",
    "id": "list_read",
    "groups": "list_read",
    "uname": "list_read",
    "ps": "list_read",
    "top": "list_read",
    "htop": "list_read",
    "atop": "list_read",
    "lsof": "list_read",
    "ss": "list_read",
    "netstat": "list_read",
    "ip": "list_read",
    "ifconfig": "list_read",
    "route": "list_read",
    "sort": "list_read",
    "uniq": "list_read",
    "cut": "list_read",
    "paste": "list_read",
    "join": "list_read",
    "comm": "list_read",
    "diff": "list_read",
    "cmp": "list_read",
    "md5sum": "list_read",
    "sha1sum": "list_read",
    "sha256sum": "list_read",
    "sha512sum": "list_read",
    "readlink": "list_read",
    "realpath": "list_read",
    "basename": "list_read",
    "dirname": "list_read",
    "which": "list_read",
    "whereis": "list_read",
    "type": "list_read",
    "printenv": "list_read",
    "history": "list_read",
    "journalctl": "list_read",
    "dmesg": "list_read",
    "free": "list_read",
    "uptime": "list_read",
    "date": "list_read",
    "cal": "list_read",
    "hostname": "list_read",
    "who": "list_read",
    "w": "list_read",
    "last": "list_read",
    "vmstat": "list_read",
    "iostat": "list_read",
    "mpstat": "list_read",
    "sar": "list_read",
    "strace": "list_read",
    "ltrace": "list_read",
    "nm": "list_read",
    "objdump": "list_read",
    "readelf": "list_read",
    "strings": "list_read",
    "jq": "list_read",
    "yq": "list_read",
    # search
    "grep": "search",
    "egrep": "search",
    "fgrep": "search",
    "rg": "search",
    "ag": "search",
    "ack": "search",
    "locate": "search",
    "mlocate": "search",
    "fd": "search",
    "fdfind": "search",
    # create
    "touch": "create",
    "mkdir": "create",
    "mktemp": "create",
    "ln": "create",
    "mkfifo": "create",
    # file modification
    "sed": "modify_file",
    "awk": "modify_file",
    "gawk": "modify_file",
    "perl": "modify_file",
    "patch": "modify_file",
    "vim": "modify_file",
    "vi": "modify_file",
    "nano": "modify_file",
    "emacs": "modify_file",
    "ed": "modify_file",
    "tee": "modify_file",
    "dd": "modify_file",
    "truncate": "modify_file",
    # copy / move (coreutils ``install`` copies files; package installation
    # is handled by the package-manager branches below)
    "cp": "copy",
    "install": "copy",
    "mv": "move_rename",
    "rename": "move_rename",
    # delete
    "rm": "delete",
    "rmdir": "delete",
    "unlink": "delete",
    "shred": "delete",
    # archives
    "tar": "archive_compress",
    "zip": "archive_compress",
    "unzip": "archive_compress",
    "gzip": "archive_compress",
    "gunzip": "archive_compress",
    "bzip2": "archive_compress",
    "bunzip2": "archive_compress",
    "xz": "archive_compress",
    "unxz": "archive_compress",
    "7z": "archive_compress",
    "7za": "archive_compress",
    # remote transfer / network
    "scp": "remote_transfer",
    "rsync": "remote_transfer",
    "sftp": "remote_transfer",
    "ftp": "remote_transfer",
    "ssh": "remote_transfer",
    "telnet": "remote_transfer",
    "nc": "remote_transfer",
    "ncat": "remote_transfer",
    "netcat": "remote_transfer",
    "curl": "network_fetch",
    "wget": "network_fetch",
    "http": "network_fetch",
    "https": "network_fetch",
    "aria2c": "network_fetch",
    "ping": "network_fetch",
    "traceroute": "network_fetch",
    "dig": "network_fetch",
    "nslookup": "network_fetch",
    "host": "network_fetch",
    # package installation
    "apt": "install",
    "apt-get": "install",
    "aptitude": "install",
    "dnf": "install",
    "yum": "install",
    "rpm": "install",
    "pacman": "install",
    "zypper": "install",
    "apk": "install",
    "brew": "install",
    "snap": "install",
    "flatpak": "install",
    "pip": "install",
    "pip3": "install",
    "pipx": "install",
    "npm": "install",
    "yarn": "install",
    "pnpm": "install",
    "cargo": "install",
    "gem": "install",
    "go": "run_build_test",
    "composer": "install",
    # environment
    "export": "modify_environment",
    "unset": "modify_environment",
    "alias": "modify_environment",
    "unalias": "modify_environment",
    "set": "modify_environment",
    "ulimit": "modify_environment",
    "umask": "modify_environment",
    "cd": "modify_environment",
    "pushd": "modify_environment",
    "popd": "modify_environment",
    "source": "modify_environment",
    ".": "modify_environment",
    "env": "modify_environment",
    "mount": "modify_environment",
    "umount": "modify_environment",
    "swapon": "modify_environment",
    "swapoff": "modify_environment",
    "crontab": "modify_environment",
    "sysctl": "modify_environment",
    "modprobe": "modify_environment",
    "insmod": "modify_environment",
    "rmmod": "modify_environment",
    # permissions
    "chmod": "permission_change",
    "chown": "permission_change",
    "chgrp": "permission_change",
    "setfacl": "permission_change",
    "getfacl": "list_read",
    "chattr": "permission_change",
    "lsattr": "list_read",
    "visudo": "permission_change",
    "passwd": "permission_change",
    "useradd": "permission_change",
    "userdel": "permission_change",
    "usermod": "permission_change",
    "groupadd": "permission_change",
    "groupdel": "permission_change",
    "groupmod": "permission_change",
    # process control
    "kill": "process_control",
    "pkill": "process_control",
    "killall": "process_control",
    "service": "process_control",
    "systemctl": "process_control",
    "supervisorctl": "process_control",
    "shutdown": "process_control",
    "reboot": "process_control",
    "poweroff": "process_control",
    "halt": "process_control",
    "init": "process_control",
    "telinit": "process_control",
    "docker": "process_control",
    "podman": "process_control",
    "kubectl": "process_control",
    "nohup": "process_control",
    # build/test
    "make": "run_build_test",
    "cmake": "run_build_test",
    "ninja": "run_build_test",
    "pytest": "run_build_test",
    "tox": "run_build_test",
    "nox": "run_build_test",
    "unittest": "run_build_test",
    "mvn": "run_build_test",
    "gradle": "run_build_test",
    "ant": "run_build_test",
    "jest": "run_build_test",
    "vitest": "run_build_test",
    "mocha": "run_build_test",
    "cargo": "run_build_test",
    "rustc": "run_build_test",
    "gcc": "run_build_test",
    "g++": "run_build_test",
    "clang": "run_build_test",
    "clang++": "run_build_test",
    "javac": "run_build_test",
    "java": "run_build_test",
    "node": "run_build_test",
    "deno": "run_build_test",
    "bun": "run_build_test",
    "ruby": "run_build_test",
    "python": "run_build_test",
    "python3": "run_build_test",
    "pypy3": "run_build_test",
    "bash": "run_build_test",
    "sh": "run_build_test",
    "zsh": "run_build_test",
    "dash": "run_build_test",
    "ksh": "run_build_test",
    "fish": "run_build_test",
    # databases
    "mysql": "database_change",
    "mariadb": "database_change",
    "psql": "database_change",
    "sqlite3": "database_change",
    "mongo": "database_change",
    "mongosh": "database_change",
    "redis-cli": "database_change",
}

_SQL_WRITE = re.compile(
    r"\b(drop\s+(?:database|table|schema|index|view|user)|truncate\s+table|"
    r"alter\s+table|delete\s+from|insert\s+into|update\s+\w+\s+set|"
    r"create\s+(?:database|table|user)|grant\s+|revoke\s+)\b",
    re.IGNORECASE,
)
_SQL_READ = re.compile(r"^\s*select\b", re.IGNORECASE)
_SQL_DROP = re.compile(r"\bdrop\s+(?:database|table|schema|index|view|user)\b", re.IGNORECASE)
_SQL_TRUNCATE = re.compile(r"\btruncate\s+table\b", re.IGNORECASE)
_SQL_DELETE_ALL = re.compile(r"\bdelete\s+from\s+[^;]+(?:\s+where\s+[^;]+)?", re.IGNORECASE)

_MODE_777 = re.compile(r"\b(?:0?777|0?666|0?4755|0?2755|0?1755|u\+s|g\+s|\+s)\b")
_SETUID = re.compile(r"\b(?:setuid|setgid|setcap|cap_setuid)\b", re.IGNORECASE)
_RECURSIVE_FLAG = re.compile(r"(?:^|\s)(?:-[A-Za-z]*[rR][A-Za-z]*|--recursive)(?:\s|$)")
_WILDCARD = re.compile(r"(?:^|[/\s])\*")
_FORK_BOMB = re.compile(r":\s*\(\s*\)\s*\{[^}]*:\s*\|\s*:[^}]*\}")
_PIPE_TO_SHELL = re.compile(
    r"(?:^|[|;])\s*(?:[A-Za-z0-9_./-]*/)?(?:ba|z|da|k|fi)?sh\b|"
    r"\b(?:python3?|perl|ruby|node)\s*(?:$|[<(-])",
    re.IGNORECASE,
)
_REMOTE_PIPE = re.compile(
    r"\b(?:curl|wget|fetch)\b[^|;\n]*\|\s*(?:sudo\s+)?(?:[A-Za-z0-9_./-]*/)?"
    r"(?:sh|bash|zsh|dash|ksh|fish|python3?|perl|ruby|node)\b",
    re.IGNORECASE,
)
_PROCESS_SUBSTITUTION = re.compile(
    r"\b(?:bash|sh|zsh|dash|ksh|fish)\s+<\(\s*(?:curl|wget)\b", re.IGNORECASE
)
_DEVICE_WRITE = re.compile(r"(?:>|of=)\s*/dev/(?:sd|hd|vd|nvme|mmcblk|disk|loop)", re.IGNORECASE)
_SQL_IDENTIFIER = re.compile(
    r"\b(?:from|table|into|update|database|schema|index|view)\s+([`\"'\[]?[A-Za-z_][\w.$-]*[`\"'\]]?)",
    re.IGNORECASE,
)
_HEADER_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_URL = re.compile(r"(?:https?|ftp|ssh)://[^\s'\";|]+", re.IGNORECASE)
_EMAIL_OR_HOST = re.compile(r"(?:[A-Za-z0-9._%+-]+@)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass(frozen=True)
class ActionInfo:
    """Deterministic description of one proposed shell action."""

    action_class: str
    reversibility: int
    scope: int
    privilege: int
    targets: tuple[str, ...]
    catastrophic: bool
    catastrophic_reason: str | None
    commands: tuple[str, ...]
    raw: str


def _strip_wrappers(tokens: list[str]) -> tuple[list[str], bool]:
    """Remove leading assignments and privilege/launcher wrappers.

    Returns the remaining tokens and whether a privilege wrapper was seen.
    """
    privileged = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if _HEADER_ASSIGNMENT.match(tok):
            i += 1
            continue
        name = PurePosixPath(tok).name.lower()
        if name in {"sudo", "doas", "pkexec", "runuser"}:
            privileged = True
            i += 1
            # skip wrapper flags (e.g. sudo -u root, sudo -E)
            while i < len(tokens) and tokens[i].startswith("-"):
                flag = tokens[i]
                i += 1
                if flag in {"-u", "-g", "-p", "-C", "-h", "-r", "-t", "-U"} and i < len(tokens):
                    i += 1
            continue
        if name == "su":
            privileged = True
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 1
            if i < len(tokens) and not tokens[i].startswith("-"):
                # su USER -c COMMAND: keep the command after -c
                pass
            continue
        if name in {"env", "command", "builtin", "exec", "nohup", "time", "stdbuf", "nice", "ionice"}:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                flag = tokens[i]
                i += 1
                if flag in {"-u", "-n", "-c", "-i", "-o", "-e"} and i < len(tokens):
                    i += 1
            # env VAR=value: skip assignments after env
            while i < len(tokens) and _HEADER_ASSIGNMENT.match(tokens[i]):
                i += 1
            continue
        break
    return tokens[i:], privileged


def _split_segments(command: str) -> list[str]:
    """Split a command line on shell control operators outside quotes."""
    segments: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    escaped = False
    i = 0
    while i < len(command):
        ch = command[i]
        if escaped:
            buf.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\":
            buf.append(ch)
            escaped = True
            i += 1
            continue
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in {"'", '"'}:
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if command.startswith("&&", i) or command.startswith("||", i):
            segments.append("".join(buf))
            buf = []
            i += 2
            continue
        if ch in {";", "\n", "|", "&"}:
            segments.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def _tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment, comments=False, posix=True)
    except ValueError:
        return re.findall(r"[^\s]+", segment)


def _first_command(tokens: list[str]) -> tuple[str, list[str], bool]:
    rest, privileged = _strip_wrappers(tokens)
    if not rest:
        return "", [], privileged
    name = PurePosixPath(rest[0]).name.lower()
    return name, rest, privileged


def _command_class(name: str, args: list[str], raw: str) -> str:
    if not name:
        return "other"
    if name == "find":
        if any(a in {"-delete", "-exec", "-execdir"} for a in args):
            if "-delete" in args or any(
                args[i + 1] in {"rm", "shred", "unlink"}
                for i, a in enumerate(args[:-1])
                if a in {"-exec", "-execdir"}
            ):
                return "delete"
        return "search"
    if name in {"sed", "awk", "gawk", "perl"}:
        if any(a in {"-i", "--in-place"} or a.startswith("-i") for a in args):
            return "modify_file"
        return "list_read"
    if name == "git":
        sub = args[1] if len(args) > 1 else ""
        mapping = {
            "status": "list_read",
            "log": "list_read",
            "diff": "list_read",
            "show": "list_read",
            "blame": "list_read",
            "branch": "list_read",
            "tag": "list_read",
            "remote": "list_read",
            "config": "modify_environment",
            "add": "modify_file",
            "commit": "create",
            "checkout": "modify_file",
            "switch": "modify_file",
            "restore": "modify_file",
            "reset": "modify_file",
            "clean": "delete",
            "rm": "delete",
            "mv": "move_rename",
            "clone": "network_fetch",
            "fetch": "network_fetch",
            "pull": "network_fetch",
            "push": "remote_transfer",
            "merge": "modify_file",
            "rebase": "modify_file",
            "cherry-pick": "modify_file",
            "stash": "modify_file",
            "init": "create",
            "submodule": "network_fetch",
        }
        return mapping.get(sub, "other")
    if name in {"docker", "podman"}:
        sub = args[1] if len(args) > 1 else ""
        if sub in {"ps", "images", "logs", "inspect", "stats", "top", "version", "info"}:
            return "list_read"
        if sub in {"rm", "rmi", "prune"}:
            return "delete"
        if sub in {"pull", "login", "push"}:
            return "network_fetch" if sub != "push" else "remote_transfer"
        if sub in {"run", "exec", "start", "stop", "restart", "kill", "pause", "unpause"}:
            return "process_control"
        return "other"
    if name == "kubectl":
        sub = args[1] if len(args) > 1 else ""
        if sub in {"get", "describe", "logs", "top", "explain", "api-resources", "version"}:
            return "list_read"
        if sub in {"delete", "drain", "cordon"}:
            return "delete"
        if sub in {"apply", "create", "replace", "patch", "edit", "scale", "rollout", "set"}:
            return "modify_environment"
        if sub in {"exec", "run", "port-forward", "proxy"}:
            return "process_control"
        return "other"
    if name == "systemctl":
        sub = args[1] if len(args) > 1 else ""
        if sub in {"status", "list-units", "list-unit-files", "show", "cat", "is-active", "is-enabled"}:
            return "list_read"
        return "process_control"
    if name == "service":
        return "process_control"
    if name in {"apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk"}:
        sub = args[1] if len(args) > 1 else ""
        if sub in {"list", "search", "show", "info", "policy"}:
            return "list_read"
        return "install"
    if name in {"pip", "pip3", "pipx"}:
        sub = args[1] if len(args) > 1 else ""
        if sub in {"list", "show", "freeze", "check"}:
            return "list_read"
        return "install"
    if name in {"npm", "yarn", "pnpm"}:
        sub = args[1] if len(args) > 1 else ""
        if sub in {"list", "ls", "view", "info", "outdated"}:
            return "list_read"
        if sub in {"test", "run", "start", "build"}:
            return "run_build_test"
        return "install"
    if name == "cargo":
        sub = args[1] if len(args) > 1 else ""
        if sub in {"build", "test", "run", "check", "bench", "clippy"}:
            return "run_build_test"
        return "install"
    if name == "go":
        sub = args[1] if len(args) > 1 else ""
        if sub in {"build", "test", "run", "vet", "fmt"}:
            return "run_build_test"
        return "install"
    if name in {"mysql", "mariadb", "psql", "sqlite3", "mongo", "mongosh", "redis-cli"}:
        sql = " ".join(args[1:])
        if _SQL_WRITE.search(sql):
            return "database_change"
        if _SQL_READ.search(sql):
            return "list_read"
        return "database_change"
    if _SQL_WRITE.search(raw) or _SQL_READ.search(raw):
        return "database_change" if _SQL_WRITE.search(raw) else "list_read"
    return _COMMAND_CLASSES.get(name, "other")


def _is_system_path(path: str) -> bool:
    p = path.rstrip("/") or "/"
    if p == "/":
        return True
    return any(p == prefix or p.startswith(prefix + "/") for prefix in SYSTEM_PREFIXES)


def _is_sensitive_path(path: str) -> bool:
    p = path.lower()
    return any(marker in p for marker in SENSITIVE_PATHS)


def _looks_like_path(token: str) -> bool:
    if not token or token.startswith("-"):
        return False
    if token in {".", "..", "*"}:
        return True
    if token.startswith(("/", "./", "../", "~")):
        return True
    if "/" in token:
        return True
    if re.fullmatch(r"[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8}", token):
        return True
    if _WILDCARD.search(token):
        return True
    return False


def _extract_targets(tokens: list[str], name: str, raw: str) -> tuple[str, ...]:
    targets: list[str] = []
    for tok in tokens[1:]:
        if not tok or tok.startswith("-") or tok in {"|", ";", "&&", "||"}:
            continue
        # strip redirection punctuation from path tokens
        candidate = tok.strip("'\"`")
        if _HEADER_ASSIGNMENT.match(candidate):
            lhs, _, rhs = candidate.partition("=")
            if lhs:
                targets.append(lhs)
            candidate = rhs
            if not candidate:
                continue
        if candidate.startswith("/") or candidate.startswith(("./", "../", "~")) or "/" in candidate:
            targets.append(candidate)
        elif _looks_like_path(candidate):
            targets.append(candidate)
        elif name in {"kill", "pkill", "killall", "systemctl", "service", "docker", "kubectl"}:
            targets.append(candidate)
        elif name in {"chmod", "chown", "chgrp"} and not candidate.isdigit():
            targets.append(candidate)
        elif name in {"export", "unset", "alias"}:
            targets.append(candidate.partition("=")[0])
    for url in _URL.findall(raw):
        targets.append(url)
    for sql_id in _SQL_IDENTIFIER.findall(raw):
        targets.append(sql_id.strip("`\"'[]"))
    # filter common non-targets
    cleaned: list[str] = []
    seen: set[str] = set()
    for t in targets:
        t = t.strip()
        if not t or t in seen:
            continue
        if t.isdigit() and name not in {"kill", "pkill", "killall"}:
            continue
        if t.lower() in {"true", "false", "none", "null"}:
            continue
        seen.add(t)
        cleaned.append(t)
    return tuple(cleaned)


def _scope(name: str, args: list[str], targets: tuple[str, ...], privileged: bool, raw: str) -> int:
    if privileged and name in {
        "apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk",
        "systemctl", "service", "mount", "umount", "reboot", "shutdown",
        "poweroff", "halt", "useradd", "userdel", "usermod", "groupadd",
        "groupdel", "passwd", "visudo", "sysctl", "modprobe",
    }:
        return 2
    if name in {
        "apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk",
        "brew", "snap", "flatpak", "systemctl", "service", "mount",
        "umount", "reboot", "shutdown", "poweroff", "halt", "init",
        "telinit", "useradd", "userdel", "usermod", "groupadd",
        "groupdel", "groupmod", "passwd", "visudo", "sysctl", "modprobe",
        "insmod", "rmmod", "crontab",
    }:
        return 2
    if name in {"export", "unset", "alias", "unalias", "set", "ulimit", "umask", "source", "."}:
        return 2
    if name in {"find", "grep", "rg"}:
        for t in targets:
            if t.rstrip("/") == "/" or _is_system_path(t):
                return 2
    if any(_is_system_path(t) for t in targets):
        return 2
    if _RECURSIVE_FLAG.search(raw) or _WILDCARD.search(raw):
        return 1
    if name in {"rm", "rmdir", "cp", "mv", "chmod", "chown", "chgrp", "tar", "zip", "unzip", "rsync", "scp"}:
        if len(targets) > 2:
            return 1
        if any(t.endswith("/") for t in targets):
            return 1
    if name in {"tar", "zip", "unzip", "gzip", "gunzip", "bzip2", "xz"}:
        return 1
    if _SQL_WRITE.search(raw):
        return 2
    return 0


def _privilege(name: str, args: list[str], targets: tuple[str, ...], privileged: bool, raw: str) -> int:
    if privileged:
        return 1
    if name in {
        "apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk",
        "brew", "snap", "flatpak", "systemctl", "service", "mount",
        "umount", "reboot", "shutdown", "poweroff", "halt", "init",
        "telinit", "useradd", "userdel", "usermod", "groupadd",
        "groupdel", "groupmod", "passwd", "visudo", "sysctl", "modprobe",
        "insmod", "rmmod", "crontab",
    }:
        return 1
    if name in {"chmod", "chown", "chgrp", "setfacl", "chattr"}:
        return 1 if any(_is_system_path(t) for t in targets) else 0
    if name in {"cat", "head", "tail", "less", "more", "cp", "scp", "rsync", "tar"}:
        return 1 if any(_is_sensitive_path(t) for t in targets) else 0
    if name in {"dd", "mkfs", "wipefs", "fdisk", "parted"}:
        return 1
    return 0


def _reversibility(name: str, args: list[str], targets: tuple[str, ...], action_class: str, raw: str) -> int:
    if name in {"rm", "rmdir", "unlink", "shred", "truncate", "dd", "mkfs", "wipefs", "fdisk", "parted"}:
        return 1
    if name in {"kill", "pkill", "killall", "shutdown", "reboot", "poweroff", "halt"}:
        return 1
    if name in {"mv", "rename"}:
        return 1 if any(a in {"-f", "--force"} for a in args) or len(targets) > 2 else 0
    if name in {"sed", "awk", "gawk", "perl"}:
        return 1 if any(a in {"-i", "--in-place"} or a.startswith("-i") for a in args) else 0
    if name in {"chmod", "chown", "chgrp", "setfacl", "chattr"}:
        if _MODE_777.search(raw) or _SETUID.search(raw):
            return 1
        return 1 if any(_is_system_path(t) for t in targets) else 0
    if name in {"curl", "wget"}:
        if re.search(r"\b(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)\b", raw, re.IGNORECASE):
            return 1
        if re.search(r"\b(?:-d|--data|--data-binary|--upload-file|-T)\b", raw):
            return 1
        return 0
    if name in {"scp", "rsync", "sftp", "ftp", "ssh", "nc", "ncat", "netcat"}:
        # Upload (local path first, remote destination second) is irreversible.
        remote = [t for t in targets if "@" in t or re.match(r"^[A-Za-z0-9.-]+:", t)]
        if remote and targets and targets[0] not in remote:
            return 1
        return 0
    if action_class == "database_change":
        return 1
    if action_class == "install":
        return 1
    if action_class == "delete":
        return 1
    if re.search(r"(?:^|\s)>\s*[^&]", raw) and not re.search(r">\s*/dev/null", raw):
        return 1
    if re.search(r"(?:^|\s)>>\s*[^&]", raw):
        return 0
    if action_class == "other" and raw.strip():
        return 1
    return 0


def _catastrophic(name: str, args: list[str], targets: tuple[str, ...], raw: str) -> str | None:
    text = raw.strip()
    lowered = text.lower()
    if _FORK_BOMB.search(text):
        return "fork bomb"
    if _REMOTE_PIPE.search(text) or _PROCESS_SUBSTITUTION.search(text):
        return "remote content piped into a shell"
    if _DEVICE_WRITE.search(text):
        return "raw write to a block device"
    if name in {"mkfs", "mkfs.ext4", "mkfs.xfs", "wipefs", "fdisk", "parted"}:
        return "filesystem or partition destruction"
    if name == "dd":
        if re.search(r"\bof\s*=\s*/dev/", text, re.IGNORECASE):
            return "raw disk write with dd"
    if name == "rm":
        if any(a in {"--no-preserve-root"} for a in args):
            return "recursive delete with --no-preserve-root"
        for t in targets:
            p = t.rstrip("/") or "/"
            if p in {"/", "~", "/home", "/root", "/etc", "/usr", "/bin", "/sbin", "/lib", "/boot", "/dev", "/proc", "/sys", "/var"}:
                return f"recursive delete of system path {p}"
            if _WILDCARD.search(t) and (p.startswith("/") or "/*" in p):
                return f"wildcard delete of system path {p}"
    if name in {"chmod", "chown", "chgrp"}:
        if _MODE_777.search(text) or _SETUID.search(text):
            if any(_is_system_path(t) or _is_sensitive_path(t) for t in targets):
                return "world-writable or setuid change on a system path"
        if any(_is_system_path(t) for t in targets) and _RECURSIVE_FLAG.search(text):
            return "recursive permission change on a system path"
    if name in {"tee", "echo", "printf"} and re.search(r"/etc/(?:sudoers|passwd|shadow|gshadow)", lowered):
        if re.search(r"(?:>>?|\btee\b)", text):
            return "write to a protected account database"
    if re.search(r"/etc/sudoers(?:\.d/|$)", lowered) and re.search(r"(?:>>?|\btee\b|\bvisudo\b)", text):
        return "sudoers modification"
    if name in {"cat", "head", "tail", "less", "more", "grep", "awk", "sed"}:
        if any(_is_sensitive_path(t) for t in targets) and not any(
            sink in lowered for sink in ("|", "curl", "wget", "scp", "nc ", "ssh ")
        ):
            # Reading shadow/sudoers is a privileged information access.
            if any(t.rstrip("/") in {"/etc/shadow", "/etc/gshadow"} for t in targets):
                return "read of a protected password database"
    if name in REMOTE_SINK_COMMANDS:
        if any(_is_sensitive_path(t) for t in targets):
            if name in {"curl", "wget"} and not re.search(r"\b(?:-d|--data|--upload-file|-T|-F)\b", text):
                return None
            return "credential or secret exfiltration"
    if name in {"scp", "rsync", "sftp", "ftp", "ssh", "nc", "ncat", "netcat"}:
        if any(_is_sensitive_path(t) for t in targets):
            return "credential or secret exfiltration"
    if _SQL_DROP.search(text) or _SQL_TRUNCATE.search(text):
        return "destructive SQL statement"
    if _SQL_DELETE_ALL.search(text) and not re.search(r"\bwhere\b", text, re.IGNORECASE):
        return "unbounded SQL delete"
    if re.search(r"\b(?:history\s+-c|shred\s+(?:-u\s+)?/var/log|rm\s+-rf\s+/var/log)\b", text, re.IGNORECASE):
        return "log or audit destruction"
    return None


def classify_action(command: str) -> ActionInfo:
    """Classify a proposed shell command without executing it.

    Unknown or unparseable commands are reported as ``action_class='other'``
    with ``reversibility=1`` so downstream stages can refuse to treat them as
    safe.
    """
    raw = command or ""
    if not raw.strip():
        return ActionInfo(
            action_class="other",
            reversibility=1,
            scope=1,
            privilege=0,
            targets=(),
            catastrophic=False,
            catastrophic_reason=None,
            commands=(),
            raw=raw,
        )

    class_priority = {
        "other": 0,
        "list_read": 1,
        "search": 1,
        "network_fetch": 2,
        "run_build_test": 2,
        "create": 3,
        "copy": 3,
        "move_rename": 3,
        "archive_compress": 3,
        "modify_environment": 4,
        "modify_file": 4,
        "install": 5,
        "remote_transfer": 5,
        "process_control": 6,
        "permission_change": 7,
        "delete": 8,
        "database_change": 8,
    }

    @dataclass(frozen=True)
    class _Segment:
        name: str
        tokens: tuple[str, ...]
        privileged: bool
        action_class: str
        targets: tuple[str, ...]
        reversibility: int
        scope: int
        privilege: int
        catastrophic: str | None

    segments: list[_Segment] = []
    for segment in _split_segments(raw):
        tokens = _tokens(segment)
        name, rest, privileged = _first_command(tokens)
        if not name:
            if _SQL_WRITE.search(segment) or _SQL_READ.search(segment):
                cls = "database_change" if _SQL_WRITE.search(segment) else "list_read"
                targets = _extract_targets([], "", segment)
                segments.append(
                    _Segment(
                        name="",
                        tokens=(),
                        privileged=False,
                        action_class=cls,
                        targets=targets,
                        reversibility=1 if cls == "database_change" else 0,
                        scope=2 if cls == "database_change" else 0,
                        privilege=0,
                        catastrophic=_catastrophic("", [], targets, segment),
                    )
                )
            continue

        seg_targets = _extract_targets(rest, name, segment)
        seg_class = _command_class(name, rest, segment)
        seg_rev = _reversibility(name, rest, seg_targets, seg_class, segment)
        seg_scope = _scope(name, rest, seg_targets, privileged, segment)
        seg_priv = _privilege(name, rest, seg_targets, privileged, segment)
        seg_catastrophic = _catastrophic(name, rest, seg_targets, segment)

        # Handle ``sh -c "..."`` and similar launchers by folding the inner
        # command's properties into this segment.
        if name in SHELLS and "-c" in rest:
            c_index = rest.index("-c")
            if c_index + 1 < len(rest):
                inner = " ".join(rest[c_index + 1 :])
                inner_info = classify_action(inner)
                if class_priority.get(inner_info.action_class, 0) > class_priority.get(seg_class, 0):
                    seg_class = inner_info.action_class
                seg_targets = tuple(dict.fromkeys(seg_targets + inner_info.targets))
                seg_rev = max(seg_rev, inner_info.reversibility)
                seg_scope = max(seg_scope, inner_info.scope)
                seg_priv = max(seg_priv, inner_info.privilege)
                seg_catastrophic = seg_catastrophic or inner_info.catastrophic_reason

        segments.append(
            _Segment(
                name=name,
                tokens=tuple(rest),
                privileged=privileged,
                action_class=seg_class,
                targets=seg_targets,
                reversibility=seg_rev,
                scope=seg_scope,
                privilege=seg_priv,
                catastrophic=seg_catastrophic,
            )
        )

    action_class = "other"
    if segments:
        action_class = max(
            (s.action_class for s in segments),
            key=lambda c: class_priority.get(c, 0),
        )

    targets: list[str] = []
    for seg in segments:
        targets.extend(seg.targets)
    deduped_targets = tuple(dict.fromkeys(t for t in targets if t))

    reversibility = max((s.reversibility for s in segments), default=0)
    scope = max((s.scope for s in segments), default=0)
    privilege = max((s.privilege for s in segments), default=0)
    # A multi-segment pipeline inherits the broadest scope.
    if len(segments) > 1:
        scope = max(scope, 1)

    catastrophic = _catastrophic("", [], deduped_targets, raw)
    if catastrophic is None:
        for seg in segments:
            if seg.catastrophic:
                catastrophic = seg.catastrophic
                break

    # Unknown commands must never look low-risk.
    if action_class == "other":
        reversibility = 1
        scope = max(scope, 1)

    return ActionInfo(
        action_class=action_class,
        reversibility=reversibility,
        scope=scope,
        privilege=privilege,
        targets=deduped_targets,
        catastrophic=catastrophic is not None,
        catastrophic_reason=catastrophic,
        commands=tuple(s.name for s in segments if s.name),
        raw=raw,
    )


def catastrophic_reason(command: str) -> str | None:
    """Return a human-readable reason if *command* is catastrophic."""
    return classify_action(command).catastrophic_reason

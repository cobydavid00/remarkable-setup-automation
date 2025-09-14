#!/usr/bin/env python3
import re, sys, subprocess
from pathlib import Path

ALIAS = "reMarkable"
USER = "root"
IP = "10.11.99.1"

SSH_DIR = Path.home() / ".ssh"
KNOWN_HOSTS = SSH_DIR / "known_hosts"
SSH_CONFIG = SSH_DIR / "config"
CFG_BACKUP = SSH_DIR / "config.bak"

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
LOCAL_FONT = ASSETS_DIR / "MaruBuri-Regular.otf"
REMOTE_FONT = "/usr/share/fonts/MaruBuri-Regular.otf"
LOCAL_IMAGE = ASSETS_DIR / "suspended.png"
REMOTE_IMAGE = "/usr/share/remarkable/suspended.png"

def run(args, capture=False, check=False, input_text=None):
    return subprocess.run(args, text=True, capture_output=capture, check=check, input=input_text)

def fail(msg, proc=None):
    print(msg)
    if proc:
        if getattr(proc, "stdout", ""): print("STDOUT:", proc.stdout.strip())
        if getattr(proc, "stderr", ""): print("STDERR:", proc.stderr.strip())
    sys.exit(1)

def refresh_known_hosts():
    for needle in (IP, f"[{IP}]:22", ALIAS):
        run(["ssh-keygen", "-R", needle])
    for host in (IP, ALIAS):
        scan = run(["ssh-keyscan", "-H", "-T", "5", host], capture=True)
        if scan.stdout:
            KNOWN_HOSTS.write_text((KNOWN_HOSTS.read_text(encoding="utf-8") if KNOWN_HOSTS.exists() else "") + scan.stdout, encoding="utf-8")

def pick_or_create_keypair():
    for base in ("id_ed25519", "id_rsa"):
        priv, pub = SSH_DIR / base, SSH_DIR / f"{base}.pub"
        if priv.exists() and pub.exists(): return priv, pub
    for pub in SSH_DIR.glob("*.pub"):
        priv = SSH_DIR / pub.stem
        if priv.exists(): return priv, pub
    priv, pub = SSH_DIR / "id_ed25519", SSH_DIR / "id_ed25519.pub"
    run(["ssh-keygen", "-t", "ed25519", "-f", str(priv), "-N", ""], check=True)
    return priv, pub

def ssh_opts_force_key(priv): return ["-o","StrictHostKeyChecking=yes","-o",f"IdentityFile={priv.as_posix()}","-o","IdentitiesOnly=yes"]

def check_passwordless(priv):
    tgt = f"{USER}@{IP}"
    p = run(["ssh", *ssh_opts_force_key(priv), "-o", "BatchMode=yes", tgt, "echo Connected"], capture=True)
    return p.returncode == 0 and "Connected" in (p.stdout or "")

def install_key(pub):
    tgt = f"{USER}@{IP}"
    pub_text = pub.read_text(encoding="utf-8").rstrip("\n") + "\n"
    cmd = "umask 077; mkdir -p /home/root/.ssh && touch /home/root/.ssh/authorized_keys && cat >> /home/root/.ssh/authorized_keys && chmod 700 /home/root/.ssh && chmod 600 /home/root/.ssh/authorized_keys"
    proc = run(["ssh", tgt, cmd], input_text=pub_text)
    if proc.returncode != 0: fail("Failed to install key.", proc)

def ensure_alias_config(priv):
    orig = SSH_CONFIG.read_text(encoding="utf-8") if SSH_CONFIG.exists() else ""
    if orig and not CFG_BACKUP.exists(): CFG_BACKUP.write_text(orig, encoding="utf-8")
    block = [f"Host {ALIAS}", f"  HostName {IP}", f"  User {USER}", f"  IdentityFile {priv.as_posix()}", "  IdentitiesOnly yes", "  StrictHostKeyChecking yes", ""]
    lines, start, end = orig.splitlines(), None, None
    for i,l in enumerate(lines):
        if re.match(r"^\s*Host\s+.*\breMarkable\b", l, re.I):
            start=i; j=i+1
            while j<len(lines) and not re.match(r"^\s*Host\s+", lines[j], re.I): j+=1
            end=j; break
    new = "\n".join(lines[:start]+block+lines[end:]) if start is not None else orig+("\n" if orig and not orig.endswith("\n") else "")+"\n".join(block)
    if new!=orig: SSH_CONFIG.write_text(new, encoding="utf-8")

def alias_is_configured(alias): return subprocess.run(["ssh","-G",alias],text=True,capture_output=True).returncode==0

def target_host(use_alias): return f"{USER}@{ALIAS}" if use_alias else f"{USER}@{IP}"

def ssh(cmd,use_alias,capture=False): return run(["ssh",target_host(use_alias),cmd],capture=capture)

def scp(local,remote,use_alias): return run(["scp","-O",str(local),f"{target_host(use_alias)}:{remote}"])

def setup_passwordless():
    refresh_known_hosts()
    priv,pub=pick_or_create_keypair()
    if not check_passwordless(priv): install_key(pub)
    if not check_passwordless(priv): fail("Passwordless SSH failed.")
    ensure_alias_config(priv)

def push_assets():
    use_alias=alias_is_configured(ALIAS)
    if not LOCAL_FONT.exists(): fail(f"Missing font: {LOCAL_FONT}")
    if not LOCAL_IMAGE.exists(): fail(f"Missing image: {LOCAL_IMAGE}")
    if ssh("echo ok",use_alias,capture=True).returncode!=0: fail("SSH connection failed.")
    ssh("mount -o remount,rw /",use_alias)
    ssh("mkdir -p /usr/share/fonts",use_alias)
    if "missing" in ssh(f'test -f "{REMOTE_FONT}" && echo exists || echo missing',use_alias,capture=True).stdout: scp(LOCAL_FONT,REMOTE_FONT,use_alias); ssh(f"chmod 644 {REMOTE_FONT}",use_alias)
    scp(LOCAL_IMAGE,REMOTE_IMAGE,use_alias); ssh(f"chmod 644 {REMOTE_IMAGE}",use_alias)
    ssh("command -v fc-cache >/dev/null 2>&1 && fc-cache -f || true",use_alias)
    ssh("sync",use_alias); ssh("mount -o remount,ro /",use_alias)
    ssh("/sbin/reboot",use_alias)

if __name__=="__main__":
    setup_passwordless()
    push_assets()

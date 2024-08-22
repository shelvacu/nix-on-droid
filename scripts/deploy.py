import os
import sys

GIT = "@git@/bin/git"
NIX = "@nix@/bin/nix"
NIX_HASH = "@nix@/bin/nix-hash"
RSYNC = "@rsync@/bin/rsync"

if GIT.startswith("@"):
    sys.stderr.write("Do not run this script directly, instead try: nix run .#deploy -- --help")
    sys.exit(1)

import subprocess
import re
import inspect
from typing import Never
from pathlib import Path

import click

def err(text: str) -> Never:
    sys.stderr.write(text)
    sys.exit(1)


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def run_capture(*args: str) -> str:
    proc = subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=None)
    return proc.stdout.decode("utf-8")


def log(msg: str) -> None:
    print(f"> {msg}")


@click.command()
@click.option(
    "--rsync-target",
    help="Where bootstrap zipballs and source tarball will be copied to. If given, this is passed directly to rsync so it can be a local folder, ssh path, etc. For production builds this should be a webroot directory that will be served at bootstrap-url"
)
@click.option("--bootstrap-url", help="URL where bootstrap zip files are available. Defaults to folder part of public-url if not given.")
@click.option("--arches", default=["aarch64-linux", "x86_64-linux"], help="Which architectures to build for. Default all")
@click.argument("public-url", help="The flake URL for this build. Can be a http/https URL, a file URL, or github:USER/REPO/BRANCH")
def deploy(public_url: str, rsync_target: str | None, bootstrap_url: str | None, arches: list[str]) -> None:
    """
        Builds bootstrap zip balls and source code tar ball (for usage as a channel or flake). If rsync_target is specified, uploads it to the directory specified in rsync_target. The contents of this directory should be reachable by the android device with public_url.

        Examples:

        $ nix run .#deploy -- 'https://example.com/bootstrap/source.tar.gz' --rsync-target 'user@host:/path/to/bootstrap'
        $ nix run .#deploy -- 'github:USER/nix-on-droid/BRANCH' --rsync-target 'user@host:/path/to/bootstrap' --bootstrap-url 'https://example.com/bootstrap/'
        $ nix run .#deploy -- 'file:///data/local/tmp/n-o-d/archive.tar.gz' #useful for testing. Note this is a path on the android device running the APK, not on the build machine
    """
    repo_dir = run_capture(GIT, "rev-parse", "--show-toplevel")
    os.chdir(repo_dir)
    source_file = "source.tar.gz"
    if (m := re.search("^github:(.*)/(.*)/(.*)", public_url)) is not None:
        channel_url = f"https://github.com/{m[1]}/{m[2]}/archive/{m[3]}.tar.gz"
        if bootstrap_url is None:
            err("--botstrap-url must be provided for github URLs")
    elif re.search("^(https?|file)://", public_url):
        channel_url = public_url
    else:
        err(f"unsupported url {public_url}")

    # for CI and local testing
    if (m := re.search("^file:///(.*)/archive.tar.gz$", public_url)) is not None:
        flake_url = f"/{m[1]}/unpacked"
    else:
        flake_url = public_url
    base_url = re.sub("/[^/]*$", "", public_url)
    if bootstrap_url is None:
        bootstrap_url = base_url

    log(f"channel_url = {channel_url}")
    log(f"flake_url = {flake_url}")
    log(f"base_url = {base_url}")
    log(f"bootstrap_url = {bootstrap_url}")

    uploads: list[str] = []

    for arch in arches:
        log(f"building {arch} proot...")
        proot = run_capture(NIX, "build", "--no-link", "--print-out-paths", f".#prootTermux-{arch}")
        proot_hash = run_capture(NIX_HASH, "--type", "sha256", "--sri", f"{proot}/bin/proot-static")
        attrs_file = Path(f"modules/environment/login/proot-attrs/{arch}.nix")
        attrs_text = inspect.cleandoc(f'''
            # WARNING: This file is autogenerated by the deploy script. Any changes will be overridden
            {{
                url = "{bootstrap_url}/bootstrap-{arch}.zip";
                hash = "{proot_hash}";
            }}
        ''')
        write_attrs_file = True
        if not attrs_file.exists():
            log(f"warn: {attrs_file} not present; creating")
        elif (old_attrs_text := attrs_file.read_text(encoding="utf-8")) != attrs_text:
            log(f"updating contents of {attrs_file}")
            print("<<<<<<")
            print(old_attrs_text)
            print("======")
            print(attrs_text)
            print(">>>>>>")
        else:
            write_attrs_file = False
            log(f"no changes needed to {attrs_file}")

        if write_attrs_file:
            attrs_file.write_text(attrs_text, newline="\n", encoding="utf-8")
            log(f"adding {attrs_file} to git index")
            run(GIT, "add", str(attrs_file))

        bootstrap_zip_store_path = run_capture(NIX, "build", "--no-link", "--print-out-paths", "--impure", f".#bootstrapZip-{arch}")
        uploads.append(bootstrap_zip_store_path + f"/bootstrap-{arch}.zip")

    log("creating tarball of current HEAD")
    run(GIT, "archive", "--prefix", "nix-on-droid/", "--output", source_file, "HEAD")
    uploads.append(source_file)

    if rsync_target is not None:
        log("uploading artifacts...")
        run(RSYNC, "--progress", *uploads, rsync_target)
    else:
        log(f"Would have uploaded {uploads}")


if __name__ == "__main__":
    # pylint can't handle the decorated function
    # pylint: disable=no-value-for-parameter
    deploy()

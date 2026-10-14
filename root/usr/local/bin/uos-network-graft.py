#!/usr/local/bin/python3
"""
Overlay the standalone UniFi Network release on the version bundled in the
UOS Server image when the standalone one is newer. The bundle lags the
Network release and a backup refuses to restore into an older controller.

The standalone package strips the UOS-only code: the gRPC/protobuf/kotlin
jars and the unifi-core proto stubs under com/unifi/**. Those are carried
over from the bundled Spring Boot fat jar into lib/extra/, which the s6 run
script adds to the classpath. Nothing else from the old build is reused:
its obfuscated class names differ per build and Spring's component scan
would instantiate stale beans.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

UNIFI_DIR = "/usr/share/unifi"
API = ("https://fw-update.ui.com/api/firmware-latest"
       "?filter=eq~~product~~unifi-controller&filter=eq~~channel~~release")
TMP = "/var/tmp/unifi-standalone"
ZIP = TMP + ".zip"
# Fat-jar libs never needed on the thin classpath.
SKIP_JARS = ("internal-dependencies", "spring-boot-jarmode-tools")


def vtuple(v):
    return tuple(int(x) for x in re.match(r"[\d.]+", v).group(0).strip(".").split("."))


def stem(name):
    return re.sub(r"-\d[\w.\-]*\.jar$", "", name).removesuffix(".jar")


def bundled_version():
    with open(f"{UNIFI_DIR}/webapps/ROOT/app-unifi/manifest.json") as f:
        return json.load(f)["version"].split(".0-")[0]


def standalone_release():
    out = subprocess.run(["fetch", "-qo", "-", API], check=True, capture_output=True).stdout
    for fw in json.loads(out)["_embedded"]["firmware"]:
        if fw["platform"] == "unix":
            return fw["version"].lstrip("v").split("+")[0], fw["_links"]["data"]["href"]
    sys.exit("no unix platform in unifi-controller release listing")


def main():
    old_v = bundled_version()
    new_v, url = standalone_release()
    print(f"bundled Network {old_v}, standalone release {new_v}")
    if vtuple(new_v) <= vtuple(old_v):
        print("bundle is current, nothing to graft")
        return

    subprocess.run(["fetch", "-qo", ZIP, url], check=True)
    shutil.rmtree(TMP, ignore_errors=True)
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(TMP)
    new = f"{TMP}/UniFi"

    fat = zipfile.ZipFile(f"{UNIFI_DIR}/lib/ace.jar")
    extra = f"{TMP}/extra"
    os.makedirs(extra)

    # Jars the standalone lib/local lacks, matched on the version-less stem.
    have = {stem(n) for n in os.listdir(f"{new}/lib/local")}
    carried = []
    for entry in fat.namelist():
        if not (entry.startswith("BOOT-INF/lib/") and entry.endswith(".jar")):
            continue
        name = entry.rsplit("/", 1)[1]
        if stem(name) in have or stem(name) in SKIP_JARS:
            continue
        with open(f"{extra}/{name}", "wb") as f:
            f.write(fat.read(entry))
        carried.append(name)
    print(f"carried {len(carried)} UOS-only jars: {' '.join(sorted(carried))}")

    # unifi-core proto stubs: generated classes, no Spring components.
    old_int = zipfile.ZipFile(io.BytesIO(fat.read("BOOT-INF/lib/internal-dependencies.jar")))
    new_int = set(zipfile.ZipFile(f"{new}/lib/internal/internal-dependencies.jar").namelist())
    protos = [n for n in old_int.namelist()
              if n.startswith("com/unifi/") and n not in new_int and not n.endswith("/")]
    with zipfile.ZipFile(f"{extra}/ucore-protos-{old_v}.jar", "w", zipfile.ZIP_DEFLATED) as out:
        for n in protos:
            out.writestr(n, old_int.read(n))
    print(f"carried {len(protos)} proto classes")

    for d in ("lib", "webapps", "dl", "conf"):
        shutil.rmtree(f"{UNIFI_DIR}/{d}", ignore_errors=True)
        shutil.move(f"{new}/{d}", f"{UNIFI_DIR}/{d}")
    shutil.move(extra, f"{UNIFI_DIR}/lib/extra")
    with open(f"{UNIFI_DIR}/lib/extra/GRAFT", "w") as f:
        f.write(f"bundled={old_v} standalone={new_v}\n")
    subprocess.run(["chmod", "-R", "a+rX", UNIFI_DIR], check=True)
    shutil.rmtree(TMP, ignore_errors=True)
    os.remove(ZIP)
    print(f"grafted Network {new_v}")


main()

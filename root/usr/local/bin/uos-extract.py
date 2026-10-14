#!/usr/local/bin/python3
"""
Extract the UOS Server OCI image from the self-extracting installer binary.
The installer is a Linux ELF with a ZIP appended; Python's zipfile reads
from the end and can locate it without running the binary.

Outputs the extracted rootfs to /var/tmp/uos-rootfs.

OCI whiteout files (.wh.*) are processed rather than extracted literally:
- .wh..wh..opq  — opaque whiteout: clear directory contents
- .wh.<name>    — delete <name> from the target directory
This prevents podman's overlay storage from misinterpreting them on commit.
"""
import json
import os
import tarfile
import zipfile

INSTALLER = "/var/tmp/uos-installer"
LAYERS_DIR = "/var/tmp/uos-layers"
ROOTFS_DIR = "/var/tmp/uos-rootfs"

os.makedirs(LAYERS_DIR, exist_ok=True)
os.makedirs(ROOTFS_DIR, exist_ok=True)

# Step 1: Extract image.tar from the embedded ZIP
print("Extracting image.tar from installer...")
with zipfile.ZipFile(INSTALLER) as z:
    z.extract("image.tar", LAYERS_DIR)

# Step 2: Unpack the OCI image tar
print("Unpacking OCI image...")
image_tar = os.path.join(LAYERS_DIR, "image.tar")
with tarfile.open(image_tar) as outer:
    outer.extractall(os.path.join(LAYERS_DIR, "oci"))

# Step 3: Parse OCI index -> manifest -> layer list
with open(os.path.join(LAYERS_DIR, "oci", "index.json")) as f:
    idx = json.load(f)

manifest_digest = idx["manifests"][0]["digest"].replace("sha256:", "")
manifest_path = os.path.join(LAYERS_DIR, "oci", "blobs", "sha256", manifest_digest)
with open(manifest_path) as f:
    manifest = json.load(f)

# Step 4: Extract each layer into the rootfs, processing OCI whiteouts
for layer in manifest["layers"]:
    digest = layer["digest"].replace("sha256:", "")
    layer_path = os.path.join(LAYERS_DIR, "oci", "blobs", "sha256", digest)
    print(f"Extracting layer {digest[:12]}...")
    with tarfile.open(layer_path) as t:
        for member in t.getmembers():
            basename = os.path.basename(member.name)
            dirpath = os.path.join(ROOTFS_DIR, os.path.dirname(member.name))

            if basename == ".wh..wh..opq":
                # Opaque whiteout: clear directory contents
                if os.path.isdir(dirpath):
                    for entry in os.listdir(dirpath):
                        entry_path = os.path.join(dirpath, entry)
                        if os.path.isdir(entry_path) and not os.path.islink(entry_path):
                            import shutil
                            shutil.rmtree(entry_path)
                        else:
                            os.remove(entry_path)
            elif basename.startswith(".wh."):
                # Regular whiteout: delete the named file/dir
                target = os.path.join(dirpath, basename[4:])
                if os.path.isdir(target) and not os.path.islink(target):
                    import shutil
                    shutil.rmtree(target)
                elif os.path.exists(target) or os.path.islink(target):
                    os.remove(target)
            else:
                t.extract(member, ROOTFS_DIR)

print("Done — rootfs at /var/tmp/uos-rootfs")

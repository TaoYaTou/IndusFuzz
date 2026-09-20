import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KEEP_DIRS = {"agentscope_env"}
KEEP_FILES = {".gitkeep"}

deleted_files = []
deleted_dirs = []
freed_bytes = 0
errors = []


def should_skip(path):
    rel = os.path.relpath(path, PROJECT_ROOT)
    parts = rel.replace("\\", "/").split("/")
    return any(p in KEEP_DIRS for p in parts)


for root, dirs, files in os.walk(PROJECT_ROOT, topdown=False):
    if should_skip(root):
        continue

    dirname = os.path.basename(root)
    if dirname == "__pycache__":
        for f in files:
            fp = os.path.join(root, f)
            try:
                sz = os.path.getsize(fp)
                os.remove(fp)
                deleted_files.append(fp)
                freed_bytes += sz
                print(f"DEL FILE: {fp}")
            except Exception as e:
                errors.append(f"{fp}: {e}")
        try:
            os.rmdir(root)
            deleted_dirs.append(root)
            print(f"DEL DIR : {root}")
        except Exception as e:
            errors.append(f"{root}: {e}")
        continue

    for f in files:
        if f.endswith(".pyc") or f.endswith(".pyo"):
            fp = os.path.join(root, f)
            try:
                sz = os.path.getsize(fp)
                os.remove(fp)
                deleted_files.append(fp)
                freed_bytes += sz
                print(f"DEL FILE: {fp}")
            except Exception as e:
                errors.append(f"{fp}: {e}")

print("")
print("=" * 60)
print(f"Deleted files : {len(deleted_files)}")
print(f"Deleted dirs  : {len(deleted_dirs)}")
print(f"Freed space   : {freed_bytes / 1024 / 1024:.3f} MB")
if errors:
    print(f"Errors        : {len(errors)}")
    for e in errors:
        print(f"  - {e}")
print("=" * 60)

"""The Rust kernels (crates/efo-kernels, module efo): ng-route pricing and the interior-point core.

The module is built and installed by `python -m pip install --no-build-isolation .`. It records
SOURCE, a digest of the kernel sources it was built from; importing this file recomputes the
digest from the tree and refuses a module built from other sources, so a result never runs on a
stale build. The digest is the one crates/efo-py/build.rs computes: FNV-1a (64 bit) over
"path\\0text\\0" of Cargo.toml, Cargo.lock and each crate's Cargo.toml, build.rs and src/*.rs,
sorted by path, CRLF read as LF.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = "python -m pip install --no-build-isolation ."


def files(root=ROOT):
    """The kernel sources present under root, in the order build.rs digests them."""
    f = [root / "Cargo.toml", root / "Cargo.lock"]
    crates = root / "crates"
    for c in sorted(p for p in crates.iterdir() if p.is_dir()) if crates.is_dir() else []:
        f += [c / "Cargo.toml", c / "build.rs"]
        f += sorted((c / "src").glob("*.rs"))
    return [p for p in f if p.exists()]


def source(root=ROOT):
    h = 0xCBF29CE484222325
    for p in files(root):
        text = p.read_bytes().decode("utf-8", "replace").replace("\r\n", "\n")
        for b in p.relative_to(root).as_posix().encode() + b"\0" + text.encode() + b"\0":
            h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


try:
    import efo
except ImportError as e:
    raise ImportError(f"the Rust kernels are not installed; run `{BUILD}`") from e
SOURCE = source()
if efo.SOURCE != SOURCE:
    raise ImportError(f"the installed kernels were built from other sources ({efo.SOURCE}, tree "
                      f"{SOURCE}); run `{BUILD}`")

Pricer, ipm_core = efo.Pricer, efo.ipm_core

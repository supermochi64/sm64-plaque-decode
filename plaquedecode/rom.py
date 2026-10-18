"""Extract the courtyard plaque texture from your own Super Mario 64 ROM (no Nintendo data ships with this repo).

Texture: castle_grounds_textures.08800 (32x32 RGBA16, grey) inside the MIO0-compressed 'outside' texture segment.
Segment offsets per ROM version come from the public sm64 decompilation's assets.json.  The texture is byte-identical
in the US, Japanese, European and Shindou releases (SHA-1 below)."""
import hashlib, struct
import numpy as np

SEGMENT = {"us": 3534096, "jp": 3527344, "eu": 3407696, "sh": 3382064, "cn": 3455824}   # MIO0 'outside' segment offset
TEX_OFFSET, TEX_BYTES = 34816, 2048
TEX_SHA1 = "88ef618ae931725172b2e255f811a5de30b62518"


def to_z64(d: bytes) -> bytes:
    """Normalise .v64 (byte-swapped) and .n64 (little-endian) dumps to big-endian .z64."""
    m = d[:4]
    if m == bytes.fromhex("80371240"): return d
    if m == bytes.fromhex("37804012"): return bytes(b for i in range(0, len(d), 2) for b in (d[i + 1], d[i]))
    if m == bytes.fromhex("40123780"):
        a = np.frombuffer(d, "<u4").astype(">u4"); return a.tobytes()
    raise ValueError("not an N64 ROM (unknown header %s)" % m.hex())


def mio0(d, off):
    assert d[off:off + 4] == b"MIO0", "no MIO0 block at 0x%x" % off
    n, co, uo = struct.unpack(">III", d[off + 4:off + 16])
    bits, comp, raw = d[off + 16:], d[off + co:], d[off + uo:]
    out = bytearray(); bi = ci = ri = 0
    while len(out) < n:
        if bits[bi >> 3] & (0x80 >> (bi & 7)):
            out.append(raw[ri]); ri += 1
        else:
            h = (comp[ci] << 8) | comp[ci + 1]; ci += 2
            ln = (h >> 12) + 3; dist = (h & 0xFFF) + 1
            for _ in range(ln): out.append(out[-dist])
        bi += 1
    return bytes(out[:n])


def extract(rom_path):
    """-> (texture as float32 32x32 array of 5-bit grey levels 0..31, version, raw bytes)"""
    if str(rom_path).lower().endswith(".zip"):
        import zipfile
        z = zipfile.ZipFile(rom_path); d = z.read(z.namelist()[0])
    else:
        d = open(rom_path, "rb").read()
    d = to_z64(d)
    for ver, off in SEGMENT.items():
        if d[off:off + 4] != b"MIO0": continue
        raw = mio0(d, off)[TEX_OFFSET:TEX_OFFSET + TEX_BYTES]
        if hashlib.sha1(raw).hexdigest() != TEX_SHA1: continue
        v = np.frombuffer(raw, ">u2").reshape(32, 32)
        return ((v >> 11) & 31).astype(np.float32), ver, raw
    raise ValueError("plaque texture not found. Is this an unmodified Super Mario 64 ROM (US/JP/EU/Shindou/iQue)?")

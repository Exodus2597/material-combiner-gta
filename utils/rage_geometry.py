"""Export-only vertex buffer optimization for Sollumz.

Cache ordering adapted from CRCK Workshop by productofmymind,
vehicle_hierarchy_tools/compactexport.py (blob 3fd79d7c35a1112a9f1d6560804c223bc7f5113d).
https://github.com/productofmymind/CRCK-Workshop
SPDX-License-Identifier: GPL-3.0-or-later
"""
from contextlib import contextmanager
import sys
import zlib

import numpy as np


CACHE_SIZE = 16  # vertex cache size Tipsify plans for


def tipsify(indices, n, k=CACHE_SIZE):
    """Triangle order for the vertex cache: Tipsify (Sander, Nehab and Barczak, "Fast Triangle Reordering for Vertex Locality and Reduced
    Overdraw", 2007). Fans out from a vertex, then continues from the recent vertex that is still in the cache and has the fewest triangles left.
    Returns the triangles' new order (indices into the triangle list)."""
    tri = np.asarray(indices, np.int64).reshape(-1, 3)
    nt = len(tri)
    flat = tri.ravel()
    order = np.argsort(flat, kind="stable")
    adj = (order // 3).tolist()                     # triangles of each vertex, grouped by vertex
    start = np.searchsorted(flat[order], np.arange(n + 1)).tolist()
    live = np.bincount(flat, minlength=n).tolist()  # triangles not yet emitted, per vertex
    stamp = [0] * n
    tris = tri.tolist()
    emitted = bytearray(nt)
    out = []
    dead = []
    s = k + 1
    cursor = 0
    f = 0 if n else -1
    while f >= 0:
        cand = []
        for j in range(start[f], start[f + 1]):
            t = adj[j]
            if emitted[t]:
                continue
            emitted[t] = 1
            out.append(t)
            for v in tris[t]:
                dead.append(v)
                cand.append(v)
                live[v] -= 1
                if s - stamp[v] > k:
                    stamp[v] = s
                    s += 1
        best, best_p = -1, -1
        for v in cand:
            if live[v] > 0:
                p = s - stamp[v] if s - stamp[v] + 2 * live[v] <= k else 0
                if p > best_p:
                    best, best_p = v, p
        if best < 0:
            while dead:
                d = dead.pop()
                if live[d] > 0:
                    best = d
                    break
        if best < 0:
            while cursor < n and live[cursor] <= 0:
                cursor += 1
            best = cursor if cursor < n else -1
        f = best
    return np.array(out, np.int64)


def fetch_order(vertices, indices):
    """Vertices in order of first use by the triangles; (vertices, indices)."""
    idx = np.asarray(indices, np.int64)
    _, first = np.unique(idx, return_index=True)
    used = idx[np.sort(first)]                       # vertices in order of first use
    remap = np.empty(len(vertices), np.int64)
    remap[used] = np.arange(len(used))
    return vertices[used], remap[idx].astype(np.uint32)


def cache_order(vertices, indices):
    """Triangles reordered for the vertex cache, then the vertices in order of first use. Same triangles; (vertices, indices)."""
    tri = np.asarray(indices, np.int64).reshape(-1, 3)
    kept = fetch_order(vertices, indices)
    new = fetch_order(vertices, tri[tipsify(indices, len(vertices))].ravel())
    # a mesh that another tool already ordered can lose from reordering: keep the order whose buffers compress smaller
    def compressed_size(buffers):
        verts, idx = buffers
        storage = "<u2" if len(verts) <= 65536 else "<u4"
        return len(zlib.compress(verts.tobytes() + idx.astype(storage).tobytes(), 1))

    return new if compressed_size(new) < compressed_size(kept) else kept


STEPS = {"Normal": 1024, "Tangent": 1024, "Position": 8192}


def snap_vertices(vertices):
    """Snap spatial data on a copy while keeping small or narrow triangles intact."""
    snapped = vertices.copy()
    for name in snapped.dtype.names:
        if name not in STEPS and not name.startswith("TexCoord"):
            continue
        values = snapped[name]
        scale = STEPS.get(name, 4096)
        np.rint(values * scale, out=values)
        values /= scale
        values[values == 0] = 0

    if "Position" in snapped.dtype.names:
        old = vertices["Position"].reshape(-1, 3, 3).astype(np.float64)
        new = snapped["Position"].reshape(-1, 3, 3).astype(np.float64)
        old_normal = np.cross(old[:, 1] - old[:, 0], old[:, 2] - old[:, 0])
        new_normal = np.cross(new[:, 1] - new[:, 0], new[:, 2] - new[:, 0])
        if np.any(np.any(old_normal != 0, axis=1) & (np.sum(old_normal * new_normal, axis=1) <= 0)):
            snapped["Position"] = vertices["Position"]
    for name in snapped.dtype.names:
        if not name.startswith("TexCoord"):
            continue
        old = vertices[name].reshape(-1, 3, 2).astype(np.float64)
        new = snapped[name].reshape(-1, 3, 2).astype(np.float64)
        a, b = old[:, 1] - old[:, 0], old[:, 2] - old[:, 0]
        old_det = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
        a, b = new[:, 1] - new[:, 0], new[:, 2] - new[:, 0]
        new_det = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
        if np.any((abs(old_det) > 1e-12) & (old_det * new_det <= 0)):
            snapped[name] = vertices[name]
    return snapped


@contextmanager
def compact_geometry(exporter):
    """Scope buffer changes to ordinary triangle geometries in this export."""
    stock = exporter.dedupe_and_get_indices
    geometry_code = exporter.create_geometries.__code__
    cloth_functions = {"_cloth_env_export", "cloth_env_export"}

    def compact(vertices):
        caller = sys._getframe(1)
        if (caller.f_code is not geometry_code or caller.f_locals.get("is_cable") is not False
                or caller.f_locals.get("char_cloth") is not None or not len(vertices) or len(vertices) % 3):
            return stock(vertices)
        material = caller.f_locals["material"].shader_properties
        frame = caller.f_back
        while frame is not None:
            if frame.f_code.co_name in cloth_functions:
                return stock(vertices)
            frame = frame.f_back
        if material.name in {"vehicle_vehglass", "vehicle_vehglass_inner"}:
            return stock(vertices)

        verts, indices = stock(snap_vertices(vertices))
        indices = indices.reshape(-1)
        if material.renderbucket in {"OPAQUE", "CUTOUT"}:
            return cache_order(verts, indices)
        return verts, indices

    exporter.dedupe_and_get_indices = compact
    try:
        yield
    finally:
        exporter.dedupe_and_get_indices = stock

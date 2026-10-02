"""Pack intact material UV rectangles without rotating or unwrapping islands."""

import math

import bpy
import numpy as np

from .packers.binary_tree_bin_packer import BinaryTreeBinPacker


def image_size(mat):
    """Resolution of images feeding color or normals, including node groups."""
    sizes = []
    visited = set()
    def visit(node):
        if node in visited:
            return
        visited.add(node)
        if node.type == "TEX_IMAGE" and node.image:
            sizes.append(tuple(node.image.size))
        if node.type == "GROUP" and node.node_tree:
            for inner in node.node_tree.nodes:
                visit(inner)
        for socket in node.inputs:
            for link in socket.links:
                visit(link.from_node)
    for node in mat.node_tree.nodes:
        if node.type in {"BSDF_PRINCIPLED", "BSDF_DIFFUSE", "EMISSION"}:
            for name in ("Base Color", "Color", "Normal"):
                socket = node.inputs.get(name)
                if socket:
                    for link in socket.links:
                        visit(link.from_node)
    sizes = [s for s in sizes if min(s) > 0]
    if not sizes:
        return 64, 64
    # Keep the primary color sheet's aspect while accommodating normal detail.
    base = sizes[0]
    scale = max(max(s[i] / base[i] for i in (0, 1)) for s in sizes)
    return tuple(math.ceil(n * scale) for n in base)


def flexible_tiles(tiles, size, padding):
    """Partition atlas space by source pixel area; keep tiny maps in a small band."""
    minimum = padding * 2 + 4
    ordered = sorted(tiles, key=lambda t: (-math.prod(t["size"]), t["name"]))
    def divide(items, x, y, w, h):
        if len(items) == 1:
            if min(w, h) < minimum:
                raise ValueError("Too many material tiles for this atlas size/padding")
            return [(items[0], (x + padding, size - y - h + padding, w - 2 * padding, h - 2 * padding))]
        weights = [math.prod(t["size"]) for t in items]
        total = sum(weights)
        cumulative = np.cumsum(weights)[:-1]
        index = int(np.argmin(abs(cumulative - total / 2))) + 1
        fraction = float(cumulative[index - 1] / total)
        for horizontal in (w >= h, w < h):
            length, cross = (w, h) if horizontal else (h, w)
            capacity = cross // minimum
            if not capacity:
                continue
            low = minimum * math.ceil(index / capacity)
            high = length - minimum * math.ceil((len(items) - index) / capacity)
            if low > high:
                continue
            cut = max(low, min(high, round(length * fraction)))
            try:
                if horizontal:
                    return divide(items[:index], x, y, cut, h) + divide(items[index:], x + cut, y, w - cut, h)
                return divide(items[:index], x, y, w, cut) + divide(items[index:], x, y + cut, w, h - cut)
            except ValueError:
                continue
        # Near the padding limit, a grid fits cases a weighted split cannot.
        columns = min(w // minimum, max(1, math.ceil(math.sqrt(len(items) * w / h))))
        if not columns or not h // minimum:
            raise ValueError("Too many material tiles for this atlas size/padding")
        columns = max(columns, math.ceil(len(items) / (h // minimum)))
        rows = math.ceil(len(items) / columns)
        if columns > w // minimum or rows > h // minimum:
            raise ValueError("Too many material tiles for this atlas size/padding")
        result = []
        for row in range(rows):
            group = items[row * columns:(row + 1) * columns]
            top, bottom = y + h * row // rows, y + h * (row + 1) // rows
            for column, tile in enumerate(group):
                left, right = x + w * column // len(group), x + w * (column + 1) // len(group)
                result.extend(divide([tile], left, top, right - left, bottom - top))
        return result
    tiny = [t for t in ordered if max(t["size"]) <= 64]
    main = [t for t in ordered if max(t["size"]) > 64]
    result = None
    if tiny and main:
        cell = math.ceil(max(max(t["size"]) for t in tiny)) + padding * 2
        cell = max(cell, minimum)
        rows = size // cell
        if rows:
            band = math.ceil(len(tiny) / rows) * cell
            if size - band >= minimum:
                try:
                    result = divide(main, 0, 0, size - band, size)
                    result += [(t, (size - band + (i // rows) * cell + padding,
                                     size - (i % rows + 1) * cell + padding,
                                     cell - padding * 2, cell - padding * 2)) for i, t in enumerate(tiny)]
                except ValueError:
                    result = None
    if result is None:
        result = divide(ordered, 0, 0, size, size)
    for tile, rect in result:
        tile["rect"] = rect


def pack_tiles(tiles, size, padding, flexible=True):
    """Reuse the existing non-rotating packer; maximize common texture scale."""
    if flexible:
        flexible_tiles(tiles, size, padding)
        return
    ordered = sorted(tiles, key=lambda t: (-max(t["size"]), -math.prod(t["size"]), t["name"]))
    def fit(scale):
        packer = BinaryTreeBinPacker()
        root = {"x": 0, "y": 0, "w": size, "h": size}
        result = []
        for tile in ordered:
            w, h = (max(4, int(n * scale)) for n in tile["size"])
            node = packer.find_node(root, w + padding * 2, h + padding * 2)
            if node is None:
                return None
            packer.split_node(node, w + padding * 2, h + padding * 2)
            result.append((tile, (node["x"] + padding, size - node["y"] - padding - h, w, h)))
        return result
    if fit(0) is None:
        raise ValueError("Too many material tiles for this atlas size/padding")
    low, high = 0.0, size / max(max(t["size"]) for t in tiles)
    best = fit(0)
    for _ in range(24):
        middle = (low + high) / 2
        candidate = fit(middle)
        if candidate is None:
            high = middle
        else:
            low, best = middle, candidate
    for tile, rect in best:
        tile["rect"] = rect


def arrange_material_tiles(objects, atlas_uv, size, padding, flexible=True):
    tiles = []
    for obj in objects:
        source = next(u for u in obj.data.uv_layers if u.active_render)
        for index in sorted({p.material_index for p in obj.data.polygons}):
            loops = [i for p in obj.data.polygons if p.material_index == index for i in p.loop_indices]
            coords = np.array([tuple(source.data[i].uv) for i in loops], dtype=np.float64)
            # Keep the entire original 0..1 sheet, including unused texture areas.
            low = np.floor(np.minimum(coords.min(0) + 1e-6, 0))
            high = np.ceil(np.maximum(coords.max(0) - 1e-6, 1))
            extent = high - low
            material = obj.material_slots[index].material
            dims = image_size(material)
            tiles.append({"object": obj, "material": material, "name": material.name,
                          "loops": loops, "source": source.name, "low": low, "extent": extent,
                          "size": tuple(dims[i] * extent[i] for i in (0, 1))})
    pack_tiles(tiles, size, padding, flexible)
    for tile in tiles:
        obj = tile["object"]
        x, y, w, h = tile["rect"]
        source = obj.data.uv_layers[tile["source"]]
        target = obj.data.uv_layers[atlas_uv]
        for i in tile["loops"]:
            uv = (np.array(source.data[i].uv) - tile["low"]) / tile["extent"]
            target.data[i].uv = tuple((np.array((x, y)) + uv * (w, h)) / size)
    return tiles


def tile_proxy(context, tile, atlas_uv, size):
    """Fill the complete texture sheet, not only UV areas used by the model."""
    mesh = bpy.data.meshes.new("__smc_tile")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new("__smc_tile", mesh)
    context.collection.objects.link(obj)
    mesh.materials.append(tile["material"])
    corners = np.array(((0, 0), (1, 0), (1, 1), (0, 1)), dtype=np.float64)
    x, y, w, h = tile["rect"]
    for layer in tile["object"].data.uv_layers:
        uv = mesh.uv_layers.new(name=layer.name)
        coords = ((x, y) + corners * (w, h)) / size if layer.name == atlas_uv else tile["low"] + corners * tile["extent"]
        for entry, coord in zip(uv.data, coords):
            entry.uv = tuple(coord)
        uv.active_render = layer.name == tile["source"]
    for attr in tile["object"].data.color_attributes:
        color = mesh.color_attributes.new(name=attr.name, type="FLOAT_COLOR", domain="CORNER")
        color.data.foreach_set("color", np.ones(16, dtype=np.float32))
    return obj

"""Legacy A8R8G8B8 / DXT5 DDS, with a complete linear-light mip chain.

Input is Blender's bottom-up, linear RGBA float buffer. No external encoder.
"""

import struct

import numpy as np


def _bc3_blocks(rgba):
    """Encode top-down RGBA8 as DXT5, fitting color endpoints per 4x4 block."""
    h, w = rgba.shape[:2]
    padded = np.pad(rgba, ((0, (-h) % 4), (0, (-w) % 4), (0, 0)), mode="edge")
    blocks = padded.reshape((h + 3) // 4, 4, (w + 3) // 4, 4, 4)
    blocks = blocks.transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    weights = np.array([1, 0, 2 / 3, 1 / 3], dtype=np.float32)
    for start in range(0, len(blocks), 4096):
        chunk = blocks[start:start + 4096]
        rgb = chunk[..., :3].astype(np.float32)
        alpha = chunk[..., 3].astype(np.int16)
        n = len(chunk)

        def alpha_fit(a0, a1, eight):
            palette = np.empty((n, 8), dtype=np.int16)
            palette[:, 0], palette[:, 1] = a0, a1
            divisor = 7 if eight else 5
            for i in range(1, divisor):
                palette[:, i + 1] = ((divisor - i) * a0 + i * a1) // divisor
            if not eight:
                palette[:, 6], palette[:, 7] = 0, 255
            distances = (alpha[..., None] - palette[:, None, :]).astype(np.int32) ** 2
            indices = distances.argmin(2).astype(np.uint64)
            error = np.take_along_axis(distances, indices.astype(np.intp)[..., None], 2).sum((1, 2))
            packed = np.sum(indices << (3 * np.arange(16, dtype=np.uint64)), axis=1)
            data = np.empty((n, 8), dtype=np.uint8)
            data[:, 0], data[:, 1] = a0, a1
            data[:, 2:] = (packed[:, None] >> (8 * np.arange(6, dtype=np.uint64))).astype(np.uint8)
            return data, error

        alpha_data, alpha_error = alpha_fit(alpha.max(1), alpha.min(1), True)
        # Six-step mode can represent transparent/opaque endpoints exactly.
        inner_min = np.where(alpha > 0, alpha, 255).min(1)
        inner_max = np.where(alpha < 255, alpha, 0).max(1)
        inner_min = np.minimum(inner_min, inner_max)
        six_data, six_error = alpha_fit(inner_min, inner_max, False)
        alpha_data[six_error < alpha_error] = six_data[six_error < alpha_error]

        def color_fit(endpoints):
            q = np.rint(np.clip(endpoints, 0, 255) * np.array([31, 63, 31]) / 255).astype(np.uint16)
            codes = (q[..., 0] << 11) | (q[..., 1] << 5) | q[..., 2]
            codes.sort(axis=1)
            codes = codes[:, ::-1].copy()
            r, g, b = codes >> 11, (codes >> 5) & 63, codes & 31
            ends = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4),
                             (b << 3) | (b >> 2)), axis=2).astype(np.float32)
            palette = np.concatenate((ends, np.floor((2 * ends[:, :1] + ends[:, 1:]) / 3),
                                      np.floor((ends[:, :1] + 2 * ends[:, 1:]) / 3)), axis=1)
            distances = ((rgb[:, :, None, :] - palette[:, None, :, :]) ** 2).sum(3)
            indices = distances.argmin(2)
            error = np.take_along_axis(distances, indices[..., None], 2).sum((1, 2))
            packed = np.sum(indices.astype(np.uint32) << (2 * np.arange(16, dtype=np.uint32)), axis=1)
            data = np.empty((n, 8), dtype=np.uint8)
            data[:, :4] = codes.astype("<u2").view(np.uint8).reshape(n, 4)
            data[:, 4:] = packed.astype("<u4").view(np.uint8).reshape(n, 4)
            return data, error, indices

        # Principal-axis endpoints, then least-squares refinement of palette assignments.
        mean = rgb.mean(1, keepdims=True)
        centered = rgb - mean
        covariance = np.einsum("npi,npj->nij", centered, centered)
        axis = np.linalg.eigh(covariance)[1][..., -1]
        projection = np.einsum("npi,ni->np", centered, axis)
        endpoints = mean + np.stack((projection.min(1), projection.max(1)), axis=1)[..., None] * axis[:, None, :]
        color_data, error, indices = color_fit(endpoints)
        low, high = rgb.min(1), rgb.max(1)
        # Expanded endpoints let nearly constant colors use interpolated values
        # between RGB565 steps, including exact neutral (128,128,255) normals.
        for spread in (0, np.array([8, 4, 8])):
            offset = spread * ((low > 0) & (high < 255))
            data, candidate_error, candidate_indices = color_fit(np.stack((low - offset, high + offset), axis=1))
            better = candidate_error < error
            color_data[better], error[better], indices[better] = data[better], candidate_error[better], candidate_indices[better]
        for _ in range(4):
            a = weights[indices]
            b = 1 - a
            aa, ab, bb = (a * a).sum(1), (a * b).sum(1), (b * b).sum(1)
            ar, br = (a[..., None] * rgb).sum(1), (b[..., None] * rgb).sum(1)
            determinant = aa * bb - ab * ab
            valid = determinant > 1e-6
            endpoints = np.repeat(mean, 2, axis=1)
            endpoints[valid, 0] = ((ar * bb[:, None] - br * ab[:, None])[valid] / determinant[valid, None])
            endpoints[valid, 1] = ((br * aa[:, None] - ar * ab[:, None])[valid] / determinant[valid, None])
            data, candidate_error, indices = color_fit(endpoints)
            better = candidate_error < error
            color_data[better], error[better] = data[better], candidate_error[better]
        yield np.concatenate((alpha_data, color_data), axis=1).tobytes()


def write_dds(stream, pixels, *, normal_map=False, pixel_format="A8R8G8B8"):
    pixels = np.asarray(pixels, dtype=np.float32)
    if pixels.ndim != 3 or pixels.shape[2] != 4:
        raise ValueError("Expected an H x W x 4 RGBA buffer")
    height, width = pixels.shape[:2]
    if not all(n > 0 and n & (n - 1) == 0 for n in (width, height)):
        raise ValueError("DDS dimensions must be powers of two")
    if not np.isfinite(pixels).all():
        raise ValueError("DDS pixels contain NaN or infinity")
    if pixel_format not in {"A8R8G8B8", "DXT5"}:
        raise ValueError("DDS format must be A8R8G8B8 or DXT5")
    compressed = pixel_format == "DXT5"
    count = max(width, height).bit_length()
    pitch = ((width + 3) // 4) * ((height + 3) // 4) * 16 if compressed else width * 4
    header = [124, 0xA1007 if compressed else 0x2100F, height, width, pitch, 0, count]
    header += [0] * 11
    header += ([32, 4, struct.unpack("<I", b"DXT5")[0], 0, 0, 0, 0, 0] if compressed else
               [32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000])
    header += [0x401008 if count > 1 else 0x1000, 0, 0, 0, 0]
    stream.write(b"DDS " + struct.pack("<31I", *header))
    level = np.clip(pixels, 0, 1)
    while True:
        rgb = level[..., :3]
        srgb = rgb if normal_map else np.where(rgb <= 0.0031308, rgb * 12.92,
                                               1.055 * np.power(rgb, 1 / 2.4) - 0.055)
        rgba = np.concatenate((srgb, level[..., 3:4]), axis=2)
        encoded = np.rint(np.clip(rgba, 0, 1) * 255).astype(np.uint8)
        if compressed:
            for data in _bc3_blocks(encoded[::-1]):
                stream.write(data)
        else:
            stream.write(encoded[::-1][..., [2, 1, 0, 3]].tobytes())
        h, w = level.shape[:2]
        if h == w == 1:
            break
        if normal_map:
            vectors = level[..., :3] * 2 - 1
            reduced = vectors.reshape(max(1, h // 2), 2 if h > 1 else 1,
                                      max(1, w // 2), 2 if w > 1 else 1, 3).mean((1, 3))
            lengths = np.linalg.norm(reduced, axis=2, keepdims=True)
            np.divide(reduced, lengths, out=reduced, where=lengths > 1e-8)
            reduced[lengths[..., 0] <= 1e-8] = (0, 0, 1)
            level = np.concatenate((reduced * 0.5 + 0.5,
                                    np.ones((*reduced.shape[:2], 1), dtype=np.float32)), axis=2)
            continue
        # Filter color in linear light with premultiplied alpha.
        premult = level.copy()
        premult[..., :3] *= premult[..., 3:4]
        reduced = premult.reshape(max(1, h // 2), 2 if h > 1 else 1,
                                 max(1, w // 2), 2 if w > 1 else 1, 4).mean((1, 3))
        np.divide(reduced[..., :3], reduced[..., 3:4],
                  out=reduced[..., :3], where=reduced[..., 3:4] > 0)
        level = reduced

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using BIS.Core.Compression;

internal sealed class PboArchive : IDisposable
{
    internal const int AssetLimit = 256 * 1024 * 1024;
    private readonly FileStream stream;
    private readonly long start;
    internal string Prefix { get; }
    private readonly Dictionary<string, (uint Method, uint Original, uint Size, long Offset)> entries =
        new(StringComparer.OrdinalIgnoreCase);
    internal IEnumerable<string> Names => entries.Keys;

    internal PboArchive(string path)
    {
        stream = File.OpenRead(path);
        try
        {
            using var reader = new BinaryReader(stream, Encoding.UTF8, leaveOpen: true);
            string prefix = Path.GetFileNameWithoutExtension(path);
            long offset = 0;
            for (int i = 0; i < 250000; i++)
            {
                string name = ReadName(reader);
                uint method = reader.ReadUInt32(), original = reader.ReadUInt32();
                reader.ReadUInt32(); // Reserved
                reader.ReadUInt32(); // Timestamp
                uint size = reader.ReadUInt32();
                if (name.Length == 0)
                {
                    if (method == 0x56657273 && i == 0 && original == 0 && size == 0) // Vers
                    {
                        for (int j = 0; ; j++)
                        {
                            string key = ReadName(reader);
                            if (key.Length == 0) break;
                            if (j == 1024) throw new InvalidDataException("Too many PBO properties");
                            string value = ReadName(reader);
                            if (key.Equals("prefix", StringComparison.OrdinalIgnoreCase)) prefix = value;
                        }
                        continue;
                    }
                    if (method != 0 || size != 0 || original != 0)
                        throw new InvalidDataException("Invalid PBO directory terminator");
                    start = stream.Position;
                    if (offset > stream.Length - start)
                        throw new InvalidDataException("PBO entries exceed the archive size");
                    Prefix = PathKey(prefix) ?? "";
                    return;
                }
                string? keyName = PathKey(name);
                if (keyName != null && !entries.TryAdd(keyName, (method, original, size, offset)))
                    throw new InvalidDataException($"Duplicate PBO entry: {keyName}");
                offset += size;
                if (offset > stream.Length || stream.Position > 32 * 1024 * 1024)
                    throw new InvalidDataException("Invalid PBO directory size");
            }
            throw new InvalidDataException("Too many PBO entries");
        }
        catch
        {
            stream.Dispose();
            throw;
        }
    }

    internal static string? PathKey(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return null;
        string name = path.Replace('\\', '/').TrimStart('/');
        foreach (string part in name.Split('/'))
        {
            if (part.Length == 0 || part is "." or ".." || part.EndsWith('.') || part.EndsWith(' ') ||
                part.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
                return null;
            string stem = part.Split('.', 2)[0].TrimEnd().ToUpperInvariant();
            if (stem is "CON" or "PRN" or "AUX" or "NUL" ||
                (stem.Length == 4 && (stem.StartsWith("COM") || stem.StartsWith("LPT")) &&
                 "123456789¹²³".Contains(stem[3])))
                return null;
        }
        return name;
    }

    private static string ReadName(BinaryReader reader)
    {
        Span<byte> buffer = stackalloc byte[4096];
        for (int i = 0; i < buffer.Length; i++)
        {
            byte value = reader.ReadByte();
            if (value == 0) return Encoding.UTF8.GetString(buffer[..i]);
            buffer[i] = value;
        }
        throw new InvalidDataException("PBO entry name exceeds 4096 bytes");
    }

    internal Stream? Open(string name)
    {
        if (!entries.TryGetValue(name, out var entry)) return null;
        if (entry.Size > AssetLimit || (entry.Method != 0 && entry.Original > AssetLimit))
            throw new InvalidDataException("PBO member exceeds the import size limit");
        if (entry.Method != 0 && entry.Method != 0x43707273) // Cprs
            throw new InvalidDataException($"Unsupported PBO packing method for {name}");
        stream.Position = start + entry.Offset;
        byte[] bytes = new byte[entry.Size];
        stream.ReadExactly(bytes);
        if (entry.Method == 0) return new MemoryStream(bytes, writable: false);
        if (entry.Original == 0 || bytes.Length < 5)
            throw new InvalidDataException("Invalid compressed PBO member");
        using var packed = new MemoryStream(bytes, writable: false);
        if (LZSS.ReadLZSS(packed, out var raw, entry.Original, false) != bytes.Length)
            throw new InvalidDataException("Compressed PBO member length mismatch");
        return new MemoryStream(raw, writable: false);
    }

    public void Dispose() => stream.Dispose();
}

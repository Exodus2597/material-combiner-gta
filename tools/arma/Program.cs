using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;
using System.Text.Json;
using System.Text.Json.Serialization;
using BIS.Core.Config;
using BIS.P3D;
using BIS.P3D.Conversion;
using BIS.P3D.Export;
using BIS.P3D.MLOD;

var errors = Console.Error;
Console.SetError(TextWriter.Null); // Suppress upstream binary parser trace logs.
try
{
    if (args is ["list", var archive, var result])
    {
        using var pbo = new PboArchive(archive);
        var models = pbo.Names.Where(n => n.EndsWith(".p3d", StringComparison.OrdinalIgnoreCase))
                              .Order(StringComparer.OrdinalIgnoreCase).ToArray();
        File.WriteAllText(result, JsonSerializer.Serialize(models, BridgeJson.Default.StringArray));
    }
    else if (args is ["import", var source, var member, var output, var textureRoot])
        Import(source, member, output, textureRoot);
    else
        throw new ArgumentException("Invalid Arma bridge command");
    return 0;
}
catch (Exception error)
{
    errors.WriteLine(error.Message);
    return 1;
}

static void Import(string source, string member, string output, string textureRoot)
{
    using var pbo = member.Length == 0 ? null : new PboArchive(source);
    using var input = pbo == null ? File.OpenRead(source) :
        pbo.Open(member) ?? throw new InvalidDataException("Selected model no longer exists in the PBO");
    if (input.Length is < 12 or > PboArchive.AssetLimit)
        throw new InvalidDataException("Invalid P3D file size");
    Span<byte> header = stackalloc byte[12];
    input.ReadExactly(header);
    input.Position = 0;
    int version = BitConverter.ToInt32(header[4..8]);
    if (header[..4].SequenceEqual("ODOL"u8))
    {
        if (version is < 73 or > 75)
            throw new InvalidDataException($"ODOL v{version} is unsupported (expected v73–75)");
    }
    else if (!header[..4].SequenceEqual("MLOD"u8) || version != 257)
        throw new InvalidDataException("Unsupported P3D: expected Arma MLOD v257 or ODOL v73–75");
    int lodCount = BitConverter.ToInt32(header[8..12]);
    if (version == 257 && lodCount is < 1 or > 512)
        throw new InvalidDataException("Invalid MLOD LOD count");

    var model = new P3D(input);
    var lods = model.MLOD?.Lods ?? ODOL2MLOD.Convert(model.ODOL).Lods;
    var lod = lods.Where(l => Resolution.IsVisual(l.Resolution) && l.Faces.Length > 0)
                  .MinBy(l => l.Resolution) ??
        throw new InvalidDataException("P3D has no renderable LOD");
    var embedded = model.ODOL?.Lods.FirstOrDefault(l => l.Resolution == lod.Resolution)?.Materials;
    string modelName = Path.GetFileNameWithoutExtension(pbo == null ? source : member);
    string sourceFolder = Path.GetDirectoryName(source)!;
    string memberFolder = pbo == null ? "" : (Path.GetDirectoryName(member)?.Replace('\\', '/') ?? "");
    var warnings = new HashSet<string>();
    var images = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    var parts = new List<MeshPart>();
    int faceCount = 0;
    if (lod.Faces.Length > 1_000_000)
        throw new InvalidDataException("P3D visual LOD exceeds the one-million-face import limit");
    Span<byte> magic = stackalloc byte[4];
    foreach (var group in lod.Faces.GroupBy(f => (f.Texture, f.Material)))
    {
        var (texture, material) = group.Key;
        texture ??= "";
        material ??= "";
        string? normal = embedded?.FirstOrDefault(m => m.MaterialName.Equals(material, StringComparison.OrdinalIgnoreCase))
                                 ?.StageTextures.Select(s => s.Texture).FirstOrDefault(IsNormalMap);
        if (normal == null && !string.IsNullOrEmpty(material))
        {
            try
            {
                using var mat = OpenAsset(material);
                if (mat != null && mat.Length is > 4 and <= 1024 * 1024)
                {
                    mat.ReadExactly(magic);
                    mat.Position = 0;
                    var config = magic.SequenceEqual("\0raP"u8) ? new ParamFile(mat) :
                        new ConfigParser().Parse(ConfigTokenizer.Tokenize(new StreamReader(mat).ReadToEnd(), material));
                    normal = config.Root.Entries.OfType<ParamClass>()
                                   .Where(c => c.Name.StartsWith("Stage", StringComparison.OrdinalIgnoreCase))
                                   .SelectMany(c => c.Entries.OfType<ParamValue>())
                                   .Where(v => v.Name.Equals("texture", StringComparison.OrdinalIgnoreCase))
                                   .Select(v => v.Value.Value as string)
                                   .FirstOrDefault(IsNormalMap);
                }
            }
            catch (Exception error) when (error is not OutOfMemoryException)
            {
                warnings.Add($"Could not read material {material}; trying matching normal filename");
            }
        }
        if (normal == null && PboArchive.PathKey(texture) is { } baseTexture)
        {
            var stem = Path.ChangeExtension(baseTexture, null)!;
            int suffix = stem.LastIndexOf('_');
            if (suffix >= 0 && stem[(suffix + 1)..].ToLowerInvariant() is "co" or "ca")
                stem = stem[..suffix];
            foreach (var extension in new[] { ".paa", ".png" })
            {
                var guess = stem + "_nohq" + extension;
                using var candidate = OpenAsset(guess);
                if (candidate == null) continue;
                normal = guess;
                break;
            }
        }
        var part = new MeshPart {
            Name = string.IsNullOrWhiteSpace(texture) ? modelName : Path.GetFileNameWithoutExtension(texture),
            Diffuse = DecodeTexture(texture), NormalMap = DecodeTexture(normal),
            Alpha = Path.GetFileNameWithoutExtension(texture).EndsWith("_ca", StringComparison.OrdinalIgnoreCase),
        };
        var seen = new Dictionary<(int Point, int Normal, float U, float V), int>();
        var corners = new int[4];
        foreach (var face in group)
        {
            if (face.VertexCount is < 3 or > 4)
                throw new InvalidDataException("Invalid P3D polygon size");
            for (int i = 0; i < face.VertexCount; i++)
            {
                var v = face.Vertices[i];
                if ((uint)v.PointIndex >= lod.Points.Length || !float.IsFinite(v.U) || !float.IsFinite(v.V))
                    throw new InvalidDataException("Invalid P3D vertex or UV");
                var key = (v.PointIndex, v.NormalIndex, v.U, v.V);
                if (!seen.TryGetValue(key, out int index))
                {
                    index = seen.Count;
                    seen.Add(key, index);
                    var p = lod.Points[v.PointIndex];
                    if (!float.IsFinite(p.X) || !float.IsFinite(p.Y) || !float.IsFinite(p.Z))
                        throw new InvalidDataException("P3D has non-finite positions");
                    part.Positions.AddRange([p.X, p.Y, -p.Z]);
                    var n = (uint)v.NormalIndex < lod.Normals.Length ? lod.Normals[v.NormalIndex] : null;
                    var vector = n == null ? Vector3.Zero : new Vector3(-n.X, -n.Y, n.Z);
                    if (float.IsFinite(vector.LengthSquared()) && vector.LengthSquared() > 1e-12f)
                        vector = Vector3.Normalize(vector);
                    else
                        vector = Vector3.Zero;
                    part.Normals.AddRange([vector.X, vector.Y, vector.Z]);
                    part.Uvs.AddRange([v.U, v.V]);
                }
                corners[i] = index;
            }
            for (int i = 1; i < face.VertexCount - 1; i++)
                part.Indices.AddRange([corners[0], corners[i], corners[i + 1]]);
            faceCount++;
        }
        parts.Add(part);
    }
    File.WriteAllText(Path.Combine(output, "mesh.json"),
        JsonSerializer.Serialize(new MeshData(modelName, faceCount, parts, warnings.Order().ToArray()), BridgeJson.Default.MeshData));

    Stream? OpenAsset(string? reference)
    {
        if (PboArchive.PathKey(reference) is not { } key) return null;
        if (pbo != null)
        {
            string prefix = pbo.Prefix + "/";
            string trimmed = pbo.Prefix.Length > 0 && key.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                ? key[prefix.Length..] : key;
            var stream = pbo.Open(trimmed) ?? (trimmed != key ? pbo.Open(key) : null) ??
                (memberFolder.Length > 0 ? pbo.Open(memberFolder + "/" + trimmed) : null);
            if (stream != null) return stream;
            if (textureRoot.Length == 0) return null;
        }
        string root = textureRoot.Length > 0 ? textureRoot : sourceFolder;
        foreach (string candidate in new[] { key, StripPrefix(key, root) }.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            string path = root;
            foreach (string component in candidate.Split('/'))
            {
                path = Path.Combine(path, component);
                if ((!File.Exists(path) && !Directory.Exists(path)) ||
                    (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                {
                    path = "";
                    break;
                }
            }
            if (path.Length != 0 && File.Exists(path) && new FileInfo(path).Length <= PboArchive.AssetLimit)
                return File.OpenRead(path);
        }
        return null;
    }

    string? DecodeTexture(string? reference)
    {
        if (string.IsNullOrWhiteSpace(reference) || reference.StartsWith('#')) return null;
        if (images.TryGetValue(reference, out string? cached)) return cached;
        try
        {
            using var image = OpenAsset(reference);
            if (image == null) throw new FileNotFoundException();
            string filename = $"texture_{images.Count}.png";
            string path = Path.Combine(output, filename);
            if (reference.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
            {
                using var file = File.Create(path);
                image.CopyTo(file);
            }
            else if (reference.EndsWith(".paa", StringComparison.OrdinalIgnoreCase))
            {
                var metadata = new BIS.PAA.PAA(image);
                if (metadata.Width is < 1 or > 8192 || metadata.Height is < 1 or > 8192)
                    throw new InvalidDataException("PAA dimensions exceed the import limit");
                image.Position = 0;
                File.WriteAllBytes(path, PaaToPngConverter.ConvertToPng(image));
            }
            else
                throw new NotSupportedException();
            images.Add(reference, filename);
            return filename;
        }
        catch (Exception error) when (error is not OutOfMemoryException)
        {
            warnings.Add($"Texture missing or unsupported: {reference}");
            return null;
        }
    }
}

static string StripPrefix(string key, string root)
{
    string prefix = Path.GetFileName(Path.TrimEndingDirectorySeparator(root)) + "/";
    return key.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) ? key[prefix.Length..] : key;
}

static bool IsNormalMap(string? path) =>
    path != null && Path.GetFileNameWithoutExtension(path).ToLowerInvariant() is var name &&
    (name.EndsWith("_nohq") || name.EndsWith("_nopx") || name.EndsWith("_no") || name.EndsWith("_normal"));

internal sealed record MeshData(string Name, int Faces, List<MeshPart> Parts, string[] Warnings);
internal sealed class MeshPart
{
    public string Name { get; init; } = "";
    public string? Diffuse { get; init; }
    public string? NormalMap { get; init; }
    public bool Alpha { get; init; }
    public List<float> Positions { get; } = new();
    public List<float> Normals { get; } = new();
    public List<float> Uvs { get; } = new();
    public List<int> Indices { get; } = new();
}

[JsonSerializable(typeof(string[]))]
[JsonSerializable(typeof(MeshData))]
internal partial class BridgeJson : JsonSerializerContext;

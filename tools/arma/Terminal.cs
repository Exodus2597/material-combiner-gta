// The bridge does not use UKSFTA-BIS's console UI dependency.
namespace BIS.Core;
internal static class Terminal
{
    public static void Muted(string message) => System.Console.Error.WriteLine(message);
}

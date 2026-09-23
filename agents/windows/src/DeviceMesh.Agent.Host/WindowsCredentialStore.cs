using System.Security.Cryptography;
using System.Text;
using Microsoft.Extensions.Options;

namespace DeviceMesh.Agent.Host;

public sealed class WindowsCredentialStore(IOptions<AgentOptions> options)
{
    private readonly string _path = options.Value.CredentialFilePath;

    public string? TryLoad()
    {
        if (!File.Exists(_path))
        {
            return null;
        }

        var protectedBytes = File.ReadAllBytes(_path);
        var clearBytes = ProtectedData.Unprotect(
            protectedBytes,
            optionalEntropy: null,
            DataProtectionScope.CurrentUser);
        try
        {
            return Encoding.UTF8.GetString(clearBytes);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(clearBytes);
        }
    }

    public void Save(string credential)
    {
        var directory = Path.GetDirectoryName(_path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var clearBytes = Encoding.UTF8.GetBytes(credential);
        try
        {
            var protectedBytes = ProtectedData.Protect(
                clearBytes,
                optionalEntropy: null,
                DataProtectionScope.CurrentUser);
            File.WriteAllBytes(_path, protectedBytes);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(clearBytes);
        }
    }
}

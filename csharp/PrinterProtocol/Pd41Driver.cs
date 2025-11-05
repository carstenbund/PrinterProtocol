using System;
using System.IO;
using System.Net.Sockets;

namespace PrinterProtocol;

public class Pd41Driver : IPrinterDriver, IDisposable
{
    private readonly TcpClient? _client;
    private readonly StreamWriter _writer;
    private readonly bool _dryRun;
    private double _dpi = 203.0;
    private LayoutContext _context = new(0, 0, "mm", "bottom-left", "up", null);
    private const string DeviceOrigin = "bottom-left";
    private const string DeviceYDirection = "up";

    public Pd41Driver(string host, int port = 9100, bool dryRun = true)
    {
        _dryRun = dryRun;
        _client = dryRun ? null : new TcpClient(host, port);
        _writer = dryRun
            ? new StreamWriter(Console.OpenStandardOutput())
            : new StreamWriter(_client!.GetStream());
        _writer.AutoFlush = true;
    }

    private void Send(string cmd)
    {
        if (!cmd.EndsWith("\r\n"))
        {
            cmd += "\r\n";
        }
        _writer.Write(cmd);
    }

    public void ConfigureLayout(LayoutContext context)
    {
        _context = context;
        if (context.Dpi.HasValue)
        {
            _dpi = context.Dpi.Value;
        }
    }

    public void Setup(string labelName) => Send($"SETUP \"{labelName}\"");

    public void SetFont(string name, double size) => Send($"FONT \"{name}\",{(int)size}");

    public void SetAlignment(string align) => Send($"ALIGN {align}");

    public void SetDirection(string dir) => Send($"DIR {dir}");

    public void MoveTo(double x, double y)
    {
        var (xDevice, yDevice) = _context.ToDeviceCoords(DeviceOrigin, DeviceYDirection, x, y);
        Send($"PRPOS {(int)xDevice},{(int)yDevice}");
    }

    public void DrawText(string text) => Send($"PRTXT \"{text}\"");

    public void DrawBarcode(string value, string type, int width, int ratio, int height, int size)
    {
        Send($"BARSET \"{type}\",{width},{ratio},{height},{size}");
        Send($"PRBAR \"{value}\"");
    }

    public void Comment(string text) => Send($"REM -- {text} --");

    public void PrintFeed() => Send("PRINTFEED");

    public double GetDpi() => _dpi;

    public void Dispose()
    {
        _writer.Dispose();
        _client?.Dispose();
    }
}

using System;

namespace PrinterProtocol;

public class GdiDriverStub : IPrinterDriver
{
    private LayoutContext _context = new(0, 0, "mm", "bottom-left", "up", null);
    private double _dpi = 300.0;
    private const string DeviceOrigin = "top-left";
    private const string DeviceYDirection = "down";

    public void ConfigureLayout(LayoutContext context)
    {
        _context = context;
        if (context.Dpi.HasValue)
        {
            _dpi = context.Dpi.Value;
        }
    }

    public void Setup(string labelName) => Console.WriteLine($"[SETUP] {labelName}");

    public void SetFont(string name, double size) => Console.WriteLine($"[FONT] {name} {size}");

    public void SetAlignment(string align) => Console.WriteLine($"[ALIGN] {align}");

    public void SetDirection(string dir) => Console.WriteLine($"[DIR] {dir}");

    public void MoveTo(double x, double y)
    {
        var (xDevice, yDevice) = _context.ToDeviceCoords(DeviceOrigin, DeviceYDirection, x, y);
        Console.WriteLine($"[MOVE] {xDevice},{yDevice}");
    }

    public void DrawText(string text) => Console.WriteLine($"[TEXT] {text}");

    public void DrawBarcode(string value, string type, int width, int ratio, int height, int size) =>
        Console.WriteLine($"[BARCODE] {type} '{value}' {width}x{height}");

    public void Comment(string text) => Console.WriteLine($"[COMMENT] {text}");

    public void PrintFeed() => Console.WriteLine("[PRINTFEED]");

    public double GetDpi() => _dpi;
}

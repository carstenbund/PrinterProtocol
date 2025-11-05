using System;

namespace PrinterProtocol;

public class GdiDriverStub : IPrinterDriver
{
    public void Setup(string labelName) => Console.WriteLine($"[SETUP] {labelName}");

    public void SetFont(string name, double size) => Console.WriteLine($"[FONT] {name} {size}");

    public void SetAlignment(string align) => Console.WriteLine($"[ALIGN] {align}");

    public void SetDirection(string dir) => Console.WriteLine($"[DIR] {dir}");

    public void MoveTo(double x, double y) => Console.WriteLine($"[MOVE] {x},{y}");

    public void DrawText(string text) => Console.WriteLine($"[TEXT] {text}");

    public void DrawBarcode(string value, string type, int width, int ratio, int height, int size) =>
        Console.WriteLine($"[BARCODE] {type} '{value}' {width}x{height}");

    public void Comment(string text) => Console.WriteLine($"[COMMENT] {text}");

    public void PrintFeed() => Console.WriteLine("[PRINTFEED]");

    public double GetDpi() => 300.0;
}

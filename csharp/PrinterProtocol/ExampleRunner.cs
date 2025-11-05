using System.IO;
using PrinterProtocol;

class ExampleRunner
{
    static void Main()
    {
        var json = File.ReadAllText("../../../../python/examples/label.json");
        var driver = new GdiDriverStub();
        JsonCommandInterpreter.Run(json, driver);
    }
}

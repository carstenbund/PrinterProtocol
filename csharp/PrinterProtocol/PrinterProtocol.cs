using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Json.Schema;

namespace PrinterProtocol;

public interface IPrinterDriver
{
    void ConfigureLayout(LayoutContext context);
    void Setup(string labelName);
    void SetFont(string name, double size);
    void SetAlignment(string align);
    void SetDirection(string dir);
    void MoveTo(double x, double y);
    void DrawText(string text);
    void DrawBarcode(string value, string type, int width, int ratio, int height, int size);
    void Comment(string text);
    void PrintFeed();
    double GetDpi();
}

public readonly record struct LayoutContext(
    double Width,
    double Height,
    string Units,
    string Origin,
    string YDirection,
    double? Dpi)
{
    public static LayoutContext FromJson(JsonElement root)
    {
        var width = root.TryGetProperty("width", out var widthProp) && widthProp.ValueKind == JsonValueKind.Number
            ? widthProp.GetDouble()
            : 0d;
        var height = root.TryGetProperty("height", out var heightProp) && heightProp.ValueKind == JsonValueKind.Number
            ? heightProp.GetDouble()
            : 0d;
        var units = root.TryGetProperty("units", out var unitsProp) && unitsProp.ValueKind == JsonValueKind.String
            ? unitsProp.GetString()!
            : "mm";
        var origin = root.TryGetProperty("origin", out var originProp) && originProp.ValueKind == JsonValueKind.String
            ? originProp.GetString()!
            : "bottom-left";
        var yDirection = root.TryGetProperty("y_direction", out var yProp) && yProp.ValueKind == JsonValueKind.String
            ? yProp.GetString()!
            : "up";
        double? dpi = null;
        if (root.TryGetProperty("dpi", out var dpiProp) && dpiProp.ValueKind == JsonValueKind.Number)
        {
            dpi = dpiProp.GetDouble();
        }

        return new LayoutContext(width, height, units, origin, yDirection, dpi);
    }

    public (double X, double Y) ToDeviceCoords(string deviceOrigin, string deviceYDirection, double x, double y)
    {
        var canonicalUp = string.Equals(YDirection, "up", StringComparison.OrdinalIgnoreCase);
        var deviceUp = string.Equals(deviceYDirection, "up", StringComparison.OrdinalIgnoreCase);
        var canonicalOrigin = Origin.ToLowerInvariant();
        var deviceOriginNorm = deviceOrigin.ToLowerInvariant();
        if (Height > 0 && (canonicalUp != deviceUp || canonicalOrigin != deviceOriginNorm))
        {
            return (x, Height - y);
        }

        return (x, y);
    }
}

public class JsonCommandEmitter
{
    private readonly List<Dictionary<string, object?>> _commands = new();
    private readonly Dictionary<string, object?> _layout = new()
    {
        ["units"] = "mm",
        ["origin"] = "bottom-left",
        ["y_direction"] = "up"
    };

    public JsonCommandEmitter(string? source = null, string version = "1.0")
    {
        Version = version;
        Document = new Dictionary<string, object?>();
        if (!string.IsNullOrEmpty(source))
        {
            Document["source"] = source;
        }
    }

    public string Version { get; }
    public Dictionary<string, object?> Document { get; }
    public IReadOnlyList<Dictionary<string, object?>> Commands => _commands;

    public void SetLayout(
        double width,
        double height,
        string units = "mm",
        string origin = "bottom-left",
        string yDirection = "up",
        double? dpi = null)
    {
        _layout["width"] = width;
        _layout["height"] = height;
        _layout["units"] = units;
        _layout["origin"] = origin;
        _layout["y_direction"] = yDirection;
        if (dpi.HasValue)
        {
            _layout["dpi"] = dpi.Value;
        }
    }

    public JsonCommandEmitter Emit(string name, IDictionary<string, object?>? args = null)
    {
        _commands.Add(new Dictionary<string, object?>
        {
            ["name"] = name,
            ["args"] = args is null ? new Dictionary<string, object?>() : new Dictionary<string, object?>(args)
        });
        return this;
    }

    public Dictionary<string, object?> ToDictionary()
    {
        var payload = new Dictionary<string, object?>
        {
            ["version"] = Version,
            ["commands"] = _commands
        };
        foreach (var kvp in _layout)
        {
            payload[kvp.Key] = kvp.Value;
        }
        if (Document.Count > 0)
        {
            payload["document"] = Document;
        }
        return payload;
    }

    public string ToJson(bool indented = true)
    {
        var options = new JsonSerializerOptions { WriteIndented = indented };
        return JsonSerializer.Serialize(ToDictionary(), options);
    }

    public void Validate(string schemaPath)
    {
        var schemaText = File.ReadAllText(schemaPath);
        var schema = JsonSchema.FromText(schemaText);
        using var document = JsonDocument.Parse(ToJson(indented: false));
        var result = schema.Evaluate(document.RootElement, new EvaluationOptions { OutputFormat = OutputFormat.Flag });
        if (!result.IsValid)
        {
            throw new JsonException("Schema validation failed for the generated payload.");
        }
    }
}

public class JsonCommandInterpreter
{
    private readonly IPrinterDriver _driver;

    public JsonCommandInterpreter(IPrinterDriver driver)
    {
        _driver = driver;
    }

    public void Run(string json)
    {
        using var document = JsonDocument.Parse(json);
        Run(document.RootElement);
    }

    public void Run(JsonDocument document)
    {
        Run(document.RootElement);
    }

    public void Run(JsonElement root)
    {
        var context = LayoutContext.FromJson(root);
        _driver.ConfigureLayout(context);

        if (!root.TryGetProperty("commands", out var commands) || commands.ValueKind != JsonValueKind.Array)
        {
            throw new InvalidDataException("commands array missing from payload");
        }

        if (_driver is IDisposable disposable)
        {
            using (disposable)
            {
                Execute(commands);
            }
        }
        else
        {
            Execute(commands);
        }
    }

    private void Execute(JsonElement commands)
    {
        foreach (var command in commands.EnumerateArray())
        {
            if (!command.TryGetProperty("name", out var nameProperty) || nameProperty.ValueKind != JsonValueKind.String)
            {
                throw new InvalidDataException("command name must be a string");
            }

            var name = nameProperty.GetString()!;
            var args = command.TryGetProperty("args", out var argsProperty) ? argsProperty : default;

            switch (name)
            {
                case "Setup":
                    _driver.Setup(RequireString(args, "name"));
                    break;
                case "SetFont":
                    _driver.SetFont(RequireString(args, "name"), RequireDouble(args, "size"));
                    break;
                case "SetAlignment":
                    _driver.SetAlignment(RequireString(args, "align"));
                    break;
                case "SetDirection":
                    _driver.SetDirection(RequireString(args, "direction"));
                    break;
                case "MoveTo":
                    _driver.MoveTo(RequireDouble(args, "x"), RequireDouble(args, "y"));
                    break;
                case "DrawText":
                    _driver.DrawText(RequireString(args, "text"));
                    break;
                case "DrawBarcode":
                    _driver.DrawBarcode(
                        RequireString(args, "value"),
                        RequireString(args, "type"),
                        RequireInt(args, "width"),
                        RequireInt(args, "ratio"),
                        RequireInt(args, "height"),
                        RequireInt(args, "size"));
                    break;
                case "Comment":
                    _driver.Comment(RequireString(args, "text"));
                    break;
                case "PrintFeed":
                    _driver.PrintFeed();
                    break;
                default:
                    throw new NotSupportedException($"Unsupported command '{name}'");
            }
        }
    }

    private static string RequireString(JsonElement args, string name)
    {
        if (args.ValueKind != JsonValueKind.Object || !args.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String)
        {
            throw new InvalidDataException($"Command argument '{name}' must be a string");
        }
        return value.GetString()!;
    }

    private static double RequireDouble(JsonElement args, string name)
    {
        if (args.ValueKind != JsonValueKind.Object || !args.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Number)
        {
            throw new InvalidDataException($"Command argument '{name}' must be a number");
        }
        return value.GetDouble();
    }

    private static int RequireInt(JsonElement args, string name)
    {
        if (args.ValueKind != JsonValueKind.Object || !args.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Number)
        {
            throw new InvalidDataException($"Command argument '{name}' must be an integer");
        }
        return value.GetInt32();
    }

    public static void Run(string json, IPrinterDriver driver) => new JsonCommandInterpreter(driver).Run(json);

    public static void RunFile(string path, IPrinterDriver driver)
    {
        var json = File.ReadAllText(path);
        Run(json, driver);
    }
}

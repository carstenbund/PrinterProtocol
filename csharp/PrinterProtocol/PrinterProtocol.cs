using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Json.Schema;

namespace PrinterProtocol;

public interface IPrinterDriver
{
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

public class JsonCommandEmitter
{
    private readonly List<Dictionary<string, object?>> _commands = new();

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

from pd41 import LabelBuilder, pretend_feeder, build_values_from_order, PrinterClient

if __name__ == "__main__":
    order = pretend_feeder()
    values = build_values_from_order(order)

    builder = LabelBuilder()  # from previous code block
    # Dry-run to verify each command emitted:
    with PrinterClient("192.168.1.50", dry_run=True) as client:
        builder.render("scleral", values, client, style_name="default")
        for line in client.sent:
            print(line)

    # Real print:
    # with PrinterClient("192.168.1.50") as client:
    #     builder.render("scleral", values, client)



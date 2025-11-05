from pd41 import PrinterClient, LabelBuilder, pretend_feeder, build_values_from_order
from xml_template import XMLLabelTemplate

order = pretend_feeder()
values = build_values_from_order(order)

with PrinterClient("200.0.0.118", dry_run=True) as client:
    # new XML-based layout
    tmpl = XMLLabelTemplate("templates/scleral_107.xml")
    tmpl.render(values, client)

    for line in client.sent:
        print(line)


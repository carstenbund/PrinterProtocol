import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

def add_attrs(elem, attrs):
    """Set XML attributes from dict, skipping None."""
    for k, v in attrs.items():
        if v is not None:
            elem.set(k, str(v))

def make_meta(meta_dict):
    meta_elem = ET.Element("Meta")
    for key, val in meta_dict.items():
        tag = key[0].upper() + key[1:]  # capitalize first letter
        child = ET.SubElement(meta_elem, tag)
        child.text = str(val)
    return meta_elem

def make_field_or_barcode(field):
    """Generate a <Field> or <Barcode> element depending on type."""
    tag = "Field" if field["type"].lower() == "field" else "Barcode"
    attrs = {k: v for k, v in field.items() if k not in ("type", "text")}
    elem = ET.Element(tag)
    add_attrs(elem, attrs)
    if "text" in field:
        elem.text = str(field["text"])
    return elem

def build_label_template(data):
    root_data = data["LabelTemplate"]

    # root element
    root = ET.Element("LabelTemplate")
    add_attrs(root, {
        "name": root_data["name"],
        "width": root_data["width"],
        "height": root_data["height"],
        "baseFont": root_data["baseFont"],
        "units": root_data["units"]
    })

    # meta
    if "meta" in root_data:
        meta_elem = make_meta(root_data["meta"])
        root.append(meta_elem)

    # groups
    for group in root_data.get("groups", []):
        g_elem = ET.SubElement(root, "Group")
        add_attrs(g_elem, {"name": group["name"], "offsetX": group["offsetX"]})
        for field in group.get("fields", []):
            g_elem.append(make_field_or_barcode(field))

    return root

def json_to_xml(json_path, xml_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    xml_root = build_label_template(data)

    xml_str = ET.tostring(xml_root, encoding="utf-8")
    dom = minidom.parseString(xml_str)
    pretty = dom.toprettyxml(indent="  ")

    # Clean excessive empty lines from minidom output
    lines = [line for line in pretty.split("\n") if line.strip()]
    pretty = "\n".join(lines)

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(pretty)

    print(f"Saved {xml_path}")

if __name__ == "__main__":
    json_to_xml("label_template.json", "label_template.xml")


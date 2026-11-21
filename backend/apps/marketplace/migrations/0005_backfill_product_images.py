from django.db import migrations

IMAGES = {
    "Disposable surgical gloves (box of 100)": (
        "marketplace/products/gloves.jpg",
        "Wikimedia Commons · public domain",
    ),
    "Absorbable sutures 2-0": (
        "marketplace/products/sutures-absorbable.jpg",
        "Saltanat ebli · CC0",
    ),
    "Non-absorbable sutures 0 nylon": (
        "marketplace/products/sutures-nylon.jpg",
        "Saltanat · CC0",
    ),
    "Scalpel blades No. 10 (box of 100)": (
        "marketplace/products/scalpel-blades.jpg",
        "Saltanat ebli · CC0",
    ),
    "Metzenbaum scissors": (
        "marketplace/products/metzenbaum-scissors.jpg",
        "Saltanat ebli · CC0",
    ),
    "Mayo scissors (straight)": (
        "marketplace/products/mayo-scissors.jpg",
        "Saltanat ebli · CC0",
    ),
    "Curved artery forceps": (
        "marketplace/products/artery-forceps.jpg",
        "Splarka · public domain",
    ),
    "Needle holder, 14 cm": (
        "marketplace/products/needle-holder.jpg",
        "Rschiedon · CC BY-SA 3.0",
    ),
    "Retractor set, abdominal": (
        "marketplace/products/retractor.jpg",
        "Saltanat · CC0",
    ),
    "Chest drain, 28 Fr": (
        "marketplace/products/chest-drain.jpg",
        "Johntex · CC BY 2.5",
    ),
    "Surgical masks (box of 50)": (
        "marketplace/products/surgical-masks.jpg",
        "MIKI Yoshihito · CC BY 2.0",
    ),
    "Sterile drape packs": (
        "marketplace/products/sterile-drape.jpg",
        "US Air Force / John Nimmo · public domain",
    ),
    "Bone plate, titanium, 8-hole": (
        "marketplace/products/bone-plate.jpg",
        "Netha Hussain · CC BY-SA 3.0",
    ),
    "K-wires, 2.0 mm (pack of 10)": (
        "marketplace/products/k-wires.jpg",
        "Ard0 · public domain",
    ),
    "Patient warming blanket": (
        "marketplace/products/warming-blanket.jpg",
        "Dmadeo · CC BY 4.0",
    ),
    "Pulse oximeter, handheld": (
        "marketplace/products/pulse-oximeter.jpg",
        "KENPEI · CC BY-SA 3.0",
    ),
}


def backfill(apps, schema_editor):
    Product = apps.get_model("marketplace", "Product")
    for name, (image, credit) in IMAGES.items():
        Product.objects.filter(name=name, image="").update(
            image=image, image_credit=credit
        )


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0004_product_image_product_image_credit"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]

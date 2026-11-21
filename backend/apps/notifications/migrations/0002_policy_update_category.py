from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="category",
            field=models.CharField(
                choices=[
                    ("procedure_submitted", "Record submitted for review"),
                    ("procedure_approved", "Record approved"),
                    ("procedure_returned", "Record returned for correction"),
                    ("placement_update", "Training placement update"),
                    ("examiner_assigned", "Examiner assignment"),
                    ("assessment_submitted", "Assessment awaiting decision"),
                    ("assessment_result", "Assessment decision"),
                    ("assessment_correction", "Assessment corrections requested"),
                    ("policy_update", "Policy update"),
                ],
                max_length=32,
            ),
        ),
    ]

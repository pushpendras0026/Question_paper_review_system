from decimal import Decimal
from django.db import migrations, models
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_enrollment_grade'),
    ]

    operations = [
        migrations.AddField(
            model_name='exam',
            name='max_marks',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('100.00'),
                max_digits=8,
                validators=[MinValueValidator(Decimal('0.01'))],
            ),
        ),
    ]

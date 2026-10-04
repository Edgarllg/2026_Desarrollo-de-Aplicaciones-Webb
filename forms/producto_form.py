from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length


class ProductoForm(FlaskForm):
    marca = StringField('Marca', validators=[DataRequired(), Length(max=50)])
    modelo = StringField('Modelo', validators=[DataRequired(), Length(max=50)])
    anio = IntegerField('Año', validators=[DataRequired(), NumberRange(min=1990, max=2027)])
    precio = FloatField('Precio', validators=[DataRequired(), NumberRange(min=0)])
    tipo = SelectField(
        'Tipo',
        choices=[('Sedán', 'Sedán'), ('SUV', 'SUV'), ('Pickup', 'Pickup'),
                 ('Hatchback', 'Hatchback'), ('Deportivo', 'Deportivo')],
        validators=[DataRequired()]
    )
    stock = IntegerField('Stock', validators=[DataRequired(), NumberRange(min=0)])
    # Las choices de proveedor_id se asignan dinámicamente en app.py
    # (relación productos -> proveedores mediante clave foránea)
    proveedor_id = SelectField('Proveedor', coerce=int)
    submit = SubmitField('Guardar Producto')

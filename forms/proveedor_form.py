from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class ProveedorForm(FlaskForm):
    nombre_empresa = StringField('Empresa', validators=[DataRequired(), Length(max=80)])
    contacto = StringField('Contacto', validators=[DataRequired(), Length(max=80)])
    telefono = StringField('Teléfono', validators=[DataRequired(), Length(max=15)])
    submit = SubmitField('Guardar Proveedor')

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class ClienteForm(FlaskForm):
    nombre = StringField('Nombre completo', validators=[DataRequired(), Length(max=80)])
    correo = StringField('Correo', validators=[DataRequired(), Email()])
    telefono = StringField('Teléfono', validators=[DataRequired(), Length(max=15)])
    submit = SubmitField('Guardar Cliente')

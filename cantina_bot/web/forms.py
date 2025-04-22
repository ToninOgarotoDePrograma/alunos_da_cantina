from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, SelectField, TextAreaField
from wtforms.validators import DataRequired, NumberRange

class CardapioForm(FlaskForm):
    nome = StringField('Nome do Item', validators=[DataRequired()])
    preco = DecimalField('Preço', places=2, validators=[
        DataRequired(),
        NumberRange(min=0.01)
    ])
    categoria = SelectField('Categoria', choices=[
        ('marmita', 'Marmita'),
        ('lanche', 'Lanche'),
        ('bebida', 'Bebida')
    ])

class PedidoForm(FlaskForm):
    item_id = SelectField('Item', coerce=int, validators=[DataRequired()])
    quantidade = DecimalField('Quantidade', places=0, validators=[
        DataRequired(),
        NumberRange(min=1)
    ])
    observacoes = TextAreaField('Observações')
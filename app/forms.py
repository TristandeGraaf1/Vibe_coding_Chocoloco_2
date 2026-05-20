from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Wachtwoord', validators=[DataRequired()])
    submit = SubmitField('Inloggen')

class RegisterForm(FlaskForm):
    username = StringField('Gebruikersnaam', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Wachtwoord', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Bevestig wachtwoord',
        validators=[DataRequired(), EqualTo('password', message='Wachtwoorden moeten gelijk zijn')])
    submit = SubmitField('Registreren')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email bestaat al.')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Gebruikersnaam is al bezet.')

class ProductForm(FlaskForm):
    name = StringField('Productnaam', validators=[DataRequired()])
    flavor = StringField('Smaak')
    description = TextAreaField('Beschrijving')
    expiry_date = DateField('Vervaldatum')
    submit = SubmitField('Product toevoegen')

class ProductRegisterForm(FlaskForm):
    product_code = StringField('Productcode', validators=[DataRequired(), Length(min=2, max=120)])
    name = StringField('Productnaam', validators=[DataRequired(), Length(min=2, max=120)])
    expiry_date = DateField('Houdbaarheid / vervaldatum', validators=[DataRequired()])
    submit = SubmitField('Product registreren')


class TopicForm(FlaskForm):
    title = StringField('Titel', validators=[DataRequired(), Length(min=3, max=200)])
    body = TextAreaField('Bericht', validators=[Length(min=5)])
    submit = SubmitField('Plaats onderwerp')


class ReplyForm(FlaskForm):
    body = TextAreaField('Antwoord', validators=[DataRequired(), Length(min=1)])
    submit = SubmitField('Plaats antwoord')

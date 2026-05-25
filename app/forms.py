from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, DateField, SelectField, HiddenField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, Optional
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


class CheckoutForm(FlaskForm):
    full_name = StringField('Naam', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=120)])
    payment_method = SelectField(
        'Betaalmethode',
        choices=[
            ('demo', 'Demo betaling'),
            ('ideal', 'iDEAL'),
            ('card', 'Creditcard'),
            ('bancontact', 'Bancontact'),
            ('apple_pay', 'Apple Pay'),
        ],
        validators=[DataRequired()],
    )
    cart_payload = HiddenField('Winkelmand data', validators=[Optional()])
    cart_total = HiddenField('Winkelmand totaal', validators=[Optional()])
    submit = SubmitField('Betaal nu')


class ComplaintForm(FlaskForm):
    product_id = SelectField('Product', coerce=int, validators=[DataRequired()])
    title = StringField('Onderwerp', validators=[DataRequired(), Length(min=3, max=120)])
    description = TextAreaField('Klachtomschrijving', validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Klacht indienen')


class CallbackRequestForm(FlaskForm):
    phone_number = StringField('Telefoonnummer', validators=[DataRequired(), Length(min=6, max=30)])
    preferred_date = DateField('Gewenste datum', format='%Y-%m-%d', validators=[DataRequired()])
    preferred_time_slot = SelectField(
        'Gewenste tijd',
        choices=[
            ('09:00-10:00', '09:00 - 10:00'),
            ('10:00-11:00', '10:00 - 11:00'),
            ('11:00-12:00', '11:00 - 12:00'),
            ('13:00-14:00', '13:00 - 14:00'),
            ('14:00-15:00', '14:00 - 15:00'),
            ('15:00-16:00', '15:00 - 16:00'),
            ('16:00-17:00', '16:00 - 17:00'),
        ],
        validators=[DataRequired()],
    )
    notes = TextAreaField('Aanvullende informatie', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Terugbellen aanvragen')


class NewsForm(FlaskForm):
    title = StringField('Titel', validators=[DataRequired(), Length(min=3, max=200)])
    body = TextAreaField('Inhoud (HTML toegestaan)', validators=[DataRequired(), Length(min=5)])
    publish = BooleanField('Direct publiceren')
    submit = SubmitField('Maak artikel aan')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Huidig wachtwoord', validators=[DataRequired()])
    new_password = PasswordField('Nieuw wachtwoord', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Bevestig nieuw wachtwoord',
        validators=[DataRequired(), EqualTo('new_password', message='Wachtwoorden moeten gelijk zijn')])
    submit = SubmitField('Wachtwoord wijzigen')


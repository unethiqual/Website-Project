from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from config import Config
from app.db import db, User, Expense, Income, Limit
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
from dotenv import *
import random
from mail import send_email
import logging
import os
import sys

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__, template_folder='templates')
app.config.from_object(Config)
db.init_app(app)

log_filename = f"logs/{datetime.now().strftime('%d-%m-%Y')}.txt"

logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

root_logger = logging.getLogger()
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(console_handler)

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.handlers = [logging.StreamHandler(sys.stdout)]
werkzeug_logger.setLevel(logging.INFO)
werkzeug_logger.propagate = False

flask_logger = logging.getLogger('flask.app')
flask_logger.handlers = [logging.StreamHandler(sys.stdout)]
flask_logger.setLevel(logging.INFO)
flask_logger.propagate = False



with app.app_context():
    db.create_all()

load_dotenv()

@app.route('/')
def index():
    user = session.get('user')
    root_logger.info(f"Index page accessed by user: {user}")
    return render_template('index.html', user=user)


@app.route('/login_signup', methods=['GET', 'POST'])
def login_signup():
    root_logger.info(f"Login/Signup page accessed with method: {request.method}")
    if request.method == 'POST':
        mode = request.form.get('mode')
        login = request.form.get('login')
        password = request.form.get('password')
        if mode == 'login':
            user = User.query.filter_by(login=login, password=password).first()
            if user:
                root_logger.info(f"Successful login for user: {user.first_name}")
                session['user'] = user.first_name
                session['user_id'] = user.id
                return redirect(url_for('index'))
            root_logger.warning(f"Failed login attempt for login: {login}")
            flash('Неверные данные или нет такого пользователя')

        else:
            user = User.query.filter_by(login=login).first()
            if user:
                flash('Логин уже занят')
            else:
                code = random.randint(100000, 1000000)
                emaill = request.form.get('email_addr')
                user = User(
                    login=login,
                    password=password,
                    first_name=request.form.get('first_name'),
                    last_name=request.form.get('last_name'),
                    email=emaill,
                    overall_sum=0.0,
                    spent=0.0,
                    req_code=code
                )
                db.session.add(user)
                db.session.commit()
                session['user'] = user.first_name
                session['user_id'] = user.id
                session['email'] = user.email
                a = send_email(emaill, "Код подтверждения из сервиса", f"Ваш код подтверждения: {code}")
                return redirect(url_for('check_email'))
    return render_template('login_signup.html')

@app.route('/email_check', methods=['GET', 'POST'])
def check_email():
    root_logger.info(f"Email check page accessed with method: {request.method}")
    user = User.query.get(session['user_id'])
    code = user.req_code
    code_to_check = request.form.get('code')
    if code_to_check is not None:
        if int(code_to_check) == int(code):
            return redirect(url_for('index'))
        else:
            flash("Неверный код", category='warning')
    return render_template('check_email.html')


@app.route('/manage_expenses', methods=['GET', 'POST'])
def manage_expenses():
    root_logger.info(f"Manage expenses page accessed with method: {request.method}")
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            amount = float(request.form.get('amount'))
            category = request.form.get('category')
            user = User.query.get(session['user_id'])
            expense = Expense(
                user_id=session['user_id'],
                amount=amount,
                category=category,
                date=datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            )
            limit = Limit.query.filter(
                Limit.user_id == user.id,
                Limit.category == category
            ).first()
            if limit:
                expenses_alpha = Expense.query.filter(
                    Expense.user_id == user.id,
                    Expense.category == category
                ).all()
                expenses_summa = 0
                for i in expenses_alpha:
                    expenses_summa += i.amount
                if expenses_summa + amount > limit.amount:
                    flash("Warning! You have exceeded the limit!", category='warning')
            user.spent += amount
            db.session.add(expense)
        elif action == 'edit':
            expense = Expense.query.get(request.form.get('expense_id'))
            old_amount = expense.amount
            new_amount = float(request.form.get('amount'))
            expense.amount = new_amount
            expense.category = request.form.get('category')
            user = User.query.get(session['user_id'])
            user.spent += (new_amount - old_amount)
        elif action == 'delete':
            expense = Expense.query.get(request.form.get('expense_id'))
            user = User.query.get(session['user_id'])
            user.spent -= expense.amount
            db.session.delete(expense)
        db.session.commit()
    expenses = Expense.query.filter_by(user_id=session['user_id']).all()
    return render_template('manage_expenses.html', expenses=expenses)


def check_balance(user_id):
    user = User.query.get(user_id)
    return user.overall_sum > user.spent


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    root_logger.info(f"Settings page accessed with method: {request.method}")
    if 'user_id' not in session:
        return redirect(url_for('login_signup'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        fname = request.form.get('first_name')
        lname = request.form.get('last_name')
        currency = request.form.get('currency')
        if fname is not None:
            user.first_name = request.form.get('first_name')
        if lname is not None:
            user.last_name = request.form.get('last_name')
        if currency is not None:
            user.currency = request.form.get('currency')
        db.session.commit()
        session['user'] = user.first_name
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', user=user)

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    root_logger.info(f"Feedback page accessed with method: {request.method}")
    root_logger.info(f"Login/Signup page accessed with method: {request.method}")
    if request.method == 'POST':
        mode = request.form.get('mode')
        if mode == 'rate':
            user = User.query.get(session['user_id'])
            ratenum = request.form.get('ratenum')
            user.app_rate = int(ratenum)

        else:
            file = request.files['file']
            if file and allowed_file(file.filename):
                file.save(os.path.join(Config.UPLOAD_FOLDER, file.filename))
            
    return render_template('feedback.html')

@app.route('/show_plots', methods=['GET', 'POST'])
def show_plots():
    root_logger.info(f"Show plots page accessed with method: {request.method}")
    user = User.query.get(session['user_id'])
    user_id = session.get('user_id')
    start = request.form.get('start_date', '2000-01-01')
    end = request.form.get('end_date', '2100-01-01')
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.between(start, end)
    ).all()

    categories = {}
    for exp in expenses:
        categories[exp.category] = categories.get(exp.category, 0) + exp.amount

    fig, ax = plt.subplots()
    ax.bar(categories.keys(), categories.values())
    ax.set_title('Расходы по категориям')
    bar_io = io.BytesIO()
    plt.savefig(bar_io, format='png')
    bar_io.seek(0)
    bar_plot_url = base64.b64encode(bar_io.getvalue()).decode()

    fig2, ax2 = plt.subplots()
    ax2.pie(categories.values(), labels=categories.keys(), autopct='%1.1f%%')
    ax2.set_title('Диаграмма расходов')
    pie_io = io.BytesIO()
    plt.savefig(pie_io, format='png')
    pie_io.seek(0)
    pie_chart_url = base64.b64encode(pie_io.getvalue()).decode()

    have = user.overall_sum
    spent = user.spent
    currency = user.currency
    leftover = ''
    if spent > have:
        leftover = f"{have - spent} {currency}; You've spent more than planned!"
    else:
        leftover = f"{have - spent} {currency}"

    return render_template('show_plots.html', bar_plot=bar_plot_url, pie_chart=pie_chart_url, leftover=leftover)


@app.route('/manage_incomes', methods=['GET', 'POST'])
def manage_incomes():
    root_logger.info(f"Manage incomes page accessed with method: {request.method}")
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_income':
            amount = float(request.form.get('amount'))
            income = Income(
                user_id=session['user_id'],
                amount=amount,
                source=request.form.get('source'),
                date=datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            )
            user = User.query.get(session['user_id'])
            user.overall_sum += amount
            db.session.add(income)
        elif action == 'edit_income':
            income = Income.query.get(request.form.get('income_id'))
            income.amount = float(request.form.get('amount'))
            income.source = request.form.get('source')
        elif action == 'delete_income':
            income = Income.query.get(request.form.get('income_id'))
            user = User.query.get(session['user_id'])
            user.overall_sum -= income.amount
            db.session.delete(income)
        elif action == 'set_limit':
            category = request.form.get('category')
            amount = float(request.form.get('limit_amount'))
            limit = Limit.query.filter_by(user_id=session['user_id'], category=category).first()
            if limit:
                limit.amount = amount
            else:
                limit = Limit(
                    user_id=session['user_id'],
                    category=category,
                    amount=amount
                )
                db.session.add(limit)
        elif action == 'delete_limit':
            limit = Limit.query.get(request.form.get('limit_id'))
            db.session.delete(limit)
        db.session.commit()

    incomes = Income.query.filter_by(user_id=session['user_id']).all()
    limits = Limit.query.filter_by(user_id=session['user_id']).all()
    return render_template('manage_incomes_n_limits.html', incomes=incomes, limits=limits)


@app.route('/logout')
def logout():
    user = session.get('user')
    root_logger.info(f"User {user} logged out")
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    root_logger.info(f"App started")
    app.run(debug=True)

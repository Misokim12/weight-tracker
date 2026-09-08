import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weight_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='athlete')
    target_weight = db.Column(db.Float, nullable=True)

class WeightRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    weight = db.Column(db.Float, nullable=False)
    training_log = db.Column(db.Text, nullable=True)
    notes = db.Column(db.String(200), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('athlete_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user, remember=remember)
            return redirect(url_for('index'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/athlete', methods=['GET', 'POST'])
@login_required
def athlete_dashboard():
    if request.method == 'POST':
        weight = float(request.form.get('weight'))
        training_log = request.form.get('training_log')
        notes = request.form.get('notes')
        date_str = request.form.get('date')
        
        record_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
        
        record = WeightRecord(
            weight=weight,
            training_log=training_log,
            notes=notes,
            date=record_date,
            user_id=current_user.id
        )
        db.session.add(record)
        db.session.commit()
        flash('성공적으로 기록되었습니다.')
        return redirect(url_for('athlete_dashboard'))

    today = datetime.utcnow().date()
    has_today_record = WeightRecord.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first() is not None

    records = WeightRecord.query.filter_by(user_id=current_user.id).order_by(WeightRecord.date.desc()).all()
    chart_records = WeightRecord.query.filter_by(user_id=current_user.id).order_by(WeightRecord.date.asc()).all()
    
    dates_json = json.dumps([r.date.strftime('%Y-%m-%d') for r in chart_records])
    weights_json = json.dumps([r.weight for r in chart_records])
    
    return render_template('index.html',
                           records=records,
                           dates_json=dates_json,
                           weights_json=weights_json,
                           has_today_record=has_today_record)

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('지도자 권한이 필요합니다.')
        return redirect(url_for('index'))
        
    athletes = User.query.filter_by(role='athlete').all()
    athlete_data = []
    
    for athlete in athletes:
        latest_record = WeightRecord.query.filter_by(user_id=athlete.id).order_by(WeightRecord.date.desc()).first()
        chart_records = WeightRecord.query.filter_by(user_id=athlete.id).order_by(WeightRecord.date.asc()).all()
        
        dates = [r.date.strftime('%Y-%m-%d') for r in chart_records]
        weights = [r.weight for r in chart_records]
        
        athlete_data.append({
            'info': athlete,
            'latest_record': latest_record,
            'dates_json': json.dumps(dates),
            'weights_json': json.dumps(weights)
        })
        
    return render_template('admin.html', athlete_data=athlete_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

import os
import csv
from io import StringIO
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'weight.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='athlete')
    target_weight = db.Column(db.Float, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class WeightRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    weight_before = db.Column(db.Float, nullable=True)
    weight_after = db.Column(db.Float, nullable=True)
    journal = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref=db.backref('records', lazy=True, cascade='all, delete-orphan'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    if current_user.role == 'admin':
        return redirect(url_for('admin'))
    records = WeightRecord.query.filter_by(user_id=current_user.id).order_by(WeightRecord.date.desc()).all()
    
    latest_record = records[0] if records else None
    latest_weight = latest_record.weight_after if (latest_record and latest_record.weight_after) else (latest_record.weight_before if latest_record else None)
    
    remaining_weight = None
    progress_pct = 0
    if latest_weight and current_user.target_weight:
        remaining_weight = round(latest_weight - current_user.target_weight, 2)
        if remaining_weight <= 0:
            progress_pct = 100
        else:
            progress_pct = min(100, max(0, int((1 - (remaining_weight / current_user.target_weight)) * 100)))

    return render_template(
        'index.html', 
        records=records, 
        latest_weight=latest_weight, 
        remaining_weight=remaining_weight, 
        progress_pct=progress_pct
    )

@app.route('/record_weight', methods=['POST'])
@login_required
def record_weight():
    date_str = request.form.get('date')
    weight_before = request.form.get('weight_before')
    weight_after = request.form.get('weight_after')
    journal = request.form.get('journal')

    if date_str:
        record_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        new_record = WeightRecord(
            user_id=current_user.id,
            date=record_date,
            weight_before=float(weight_before) if weight_before else None,
            weight_after=float(weight_after) if weight_after else None,
            journal=journal
        )
        db.session.add(new_record)
        db.session.commit()
        flash('기록이 성공적으로 저장되었습니다.', 'success')
    return redirect(url_for('index'))

@app.route('/set_target_weight', methods=['POST'])
@login_required
def set_target_weight():
    target_weight = request.form.get('target_weight')
    if target_weight:
        current_user.target_weight = float(target_weight)
        db.session.commit()
        flash('목표 체중이 설정되었습니다.', 'success')
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            current_user.set_password(new_password)
            db.session.commit()
            flash('비밀번호가 성공적으로 변경되었습니다.', 'success')
            return redirect(url_for('index'))
    return render_template('change_password.html')

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    athletes = User.query.filter_by(role='athlete').all()
    today_str = date.today().strftime('%Y-%m-%d')
    today_date = date.today()
    records = WeightRecord.query.filter_by(date=today_date).all()
    return render_template('admin.html', athletes=athletes, records=records, today=today_str)

@app.route('/add_athlete', methods=['POST'])
@login_required
def add_athlete():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    username = request.form.get('username')
    name = request.form.get('name')
    password = request.form.get('password', '1234')

    if username:
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('이미 존재하는 아이디입니다.', 'error')
        else:
            new_user = User(username=username, name=name if name else username, role='athlete')
            new_user.set_password(password if password else '1234')
            db.session.add(new_user)
            db.session.commit()
            flash('선수가 정상적으로 등록되었습니다. (초기 비밀번호: 1234)', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_athlete/<int:user_id>', methods=['POST'])
@login_required
def delete_athlete(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('선수가 삭제되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/athlete-records/<int:user_id>')
@login_required
def athlete_records(user_id):
    athlete = User.query.get_or_404(user_id)
    records = WeightRecord.query.filter_by(user_id=user_id).order_by(WeightRecord.date.desc()).all()
    
    record_list = []
    for r in records:
        diff = round(r.weight_after - r.weight_before, 2) if (r.weight_after is not None and r.weight_before is not None) else None
        record_list.append({
            'date': r.date.strftime('%Y-%m-%d'),
            'weight_before': r.weight_before,
            'weight_after': r.weight_after,
            'diff': diff,
            'journal': r.journal
        })
        
    return jsonify({
        'name': athlete.name,
        'username': athlete.username,
        'target_weight': athlete.target_weight,
        'records': record_list
    })

@app.route('/export_csv')
@login_required
def export_csv():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['선수ID', '아이디', '이름', '날짜', '훈련 전 체중', '훈련 후 체중', '훈련일지'])
    
    records = WeightRecord.query.order_by(WeightRecord.date.desc()).all()
    for r in records:
        cw.writerow([
            r.user_id,
            r.user.username if r.user else '',
            r.user.name if (r.user and hasattr(r.user, 'name')) else '',
            r.date,
            r.weight_before,
            r.weight_after,
            r.journal
        ])
        
    output = make_response('\ufeff' + si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=weight_records.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return output

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

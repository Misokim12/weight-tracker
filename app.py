from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# 1. 앱 객체를 가장 먼저 생성합니다.
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weight.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DB 모델 ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default="athlete")
    records = db.relationship('WeightRecord', backref='athlete', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class WeightRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)
    weight_before = db.Column(db.Float, nullable=True)
    weight_after = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 라우트 ---
@app.route("/")
@login_required
def index():
    if current_user.role == "admin":
        athletes = User.query.filter_by(role="athlete").all()
        today = datetime.now().strftime('%Y-%m-%d')
        records = WeightRecord.query.filter_by(date=today).all()
        return render_template("admin.html", athletes=athletes, records=records, today=today)
    else:
        my_records = WeightRecord.query.filter_by(user_id=current_user.id).order_by(WeightRecord.date.desc()).all()
        return render_template("index.html", records=my_records)

@app.route("/add-athlete", methods=["POST"])
@login_required
def add_athlete():
    if current_user.role != "admin":
        return redirect(url_for("index"))
    
    username = request.form.get("username")
    name = request.form.get("name")
    
    if User.query.filter_by(username=username).first():
        flash("이미 존재하는 아이디입니다.", "error")
        return redirect(url_for("index"))
        
    new_athlete = User(username=username, name=name, role="athlete")
    new_athlete.set_password("123456")
    db.session.add(new_athlete)
    db.session.commit()
    flash(f"선수 {name}({username}) 등록 완료! (초기비번: 123456)", "success")
    return redirect(url_for("index"))

@app.route("/delete-athlete/<int:user_id>", methods=["POST"])
@login_required
def delete_athlete(user_id):
    if current_user.role != "admin":
        return redirect(url_for("index"))
    
    athlete = User.query.get_or_404(user_id)
    if athlete.role == "admin":
        flash("관리자 계정은 삭제할 수 없습니다.", "error")
        return redirect(url_for("index"))
        
    db.session.delete(athlete)
    db.session.commit()
    flash(f"선수 '{athlete.name}' 계정이 삭제되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/record-weight", methods=["POST"])
@login_required
def record_weight():
    date_str = request.form.get("date") or datetime.now().strftime('%Y-%m-%d')
    w_before = request.form.get("weight_before")
    w_after = request.form.get("weight_after")
    
    target_id = request.form.get("user_id") if current_user.role == "admin" else current_user.id
    
    record = WeightRecord.query.filter_by(user_id=target_id, date=date_str).first()
    if not record:
        record = WeightRecord(user_id=target_id, date=date_str)
        db.session.add(record)
        
    if w_before and w_before.strip():
        record.weight_before = float(w_before)
    if w_after and w_after.strip():
        record.weight_after = float(w_after)
        
    db.session.commit()
    flash("체중 기록이 저장되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        if not current_user.check_password(current_pw):
            flash("현재 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("change_password"))

        if len(new_pw) < 6:
            flash("새 비밀번호는 6자 이상이어야 합니다.", "error")
            return redirect(url_for("change_password"))

        if new_pw != confirm_pw:
            flash("새 비밀번호 확인이 일치하지 않습니다.", "error")
            return redirect(url_for("change_password"))

        current_user.set_password(new_pw)
        db.session.commit()
        flash("비밀번호가 성공적으로 변경되었습니다.", "success")
        return redirect(url_for("index"))

    return render_template("change_password.html")

@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    coach = User.query.filter_by(username="coach").first()
    if not coach:
        coach = User(username="coach", name="코치님", role="admin")
        coach.set_password("CHANGE_ME_NOW")
        db.session.add(coach)
        db.session.commit()
        print("관리자 생성 완료: coach")
    else:
        print("이미 관리자 계정이 존재합니다.")

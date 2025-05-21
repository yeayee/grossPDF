import os


from flask import Blueprint, redirect, url_for, render_template, flash, current_app, send_file
from flask import Blueprint, request, redirect, url_for, render_template, flash
from flask_login import login_user,  logout_user, login_required

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired
from flask_wtf.file import FileField, FileAllowed
from bson import ObjectId
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
import base64
from flask_login import logout_user
from wtforms.fields import DecimalField, DateTimeField
from datetime import datetime

from config import User  # Import User class from config

auth_bp = Blueprint('auth', __name__)


class LoginForm(FlaskForm):
    username = StringField('Username')
    password = PasswordField('Password')
    submit = SubmitField('Login')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = request.form.get('username')
        password = request.form.get('password')
        # 验证用户名和密码，部属的时候改一改
        if username == "admin" and password == "123456":  
            user = User(username)  # 创建临时 User 对象
            login_user(user)  # 使用 Flask-Login 登录用户
            flash('登录成功！', 'success')
            return redirect(url_for('auth.dashboard'))  # 重定向到后台管理页面
        else:
            flash('用户名或密码错误，请重试。', 'danger')  # 显示错误提示

    return render_template('login.html', form=form)



@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已登出。', 'success')
    return redirect(url_for('auth.login'))

class DeleteForm(FlaskForm):
    submit = SubmitField('删除')
@auth_bp.route('/dashboard')

def dashboard():
    # 获取所有书籍
    response = current_app.db.table("books").select("*").execute()

    # 转换为列表
    books = response.data if response.data else []


    delete_form = DeleteForm()  # 创建表单实例
    return render_template("dashboard.html", books=books, delete_form=delete_form)




class BookForm(FlaskForm):
    title = StringField('书籍名称', validators=[DataRequired()])
    cover = FileField('封面图片', validators=[FileAllowed(['jpg', 'png'], '仅限 JPG 或 PNG 文件！')])
    pdf_link = StringField('书籍云盘链接', validators=[DataRequired()])  # 使用 StringField 替代 FileField
    description = TextAreaField('简介', validators=[DataRequired()])
    price = DecimalField('售价', places=2, validators=[DataRequired()])  # 价格字段，保留两位小数
    published_at = DateTimeField('发布时间', format='%Y-%m-%d %H:%M:%S', default=datetime.utcnow)  # 默认使用当前时间
    submit = SubmitField('发布')

    
@auth_bp.route('/publish', methods=['GET', 'POST'])
@login_required
def publish():
    form = BookForm()
    if form.validate_on_submit():
        # 处理封面图片上传并直接存入 MongoDB
        cover_binary = None
        if form.cover.data:
            cover_file = form.cover.data
            cover_binary = cover_file.read()  # 直接读取二进制数据

        # 处理书籍信息（PDF 使用云盘链接）
        book_data = {
            'title': form.title.data,
            'cover': base64.b64encode(cover_binary).decode("utf-8"),
            'pdf_link': form.pdf_link.data,  # 存储云盘链接
            'description': form.description.data,
            'price': float(form.price.data),
            'published_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        # 插入数据到 Supabase
        response = current_app.db.table('books').insert(book_data).execute()
        flash('书籍发布成功！', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('publish.html', form=form, title='发布新书籍')

@auth_bp.route('/edit/<book_id>', methods=['GET', 'POST'])
@login_required
def edit(book_id):
    # 查询 ID 对应的书籍
    response = current_app.db.table("books").select("*").eq("id", book_id).execute()

    # 提取数据
    book = response.data[0] if response.data else None
    if not book:
        flash("书籍不存在！", "danger")
        return redirect(url_for('auth.dashboard'))

    form = BookForm(obj=book)

    if form.validate_on_submit():
        update_data = {
            "title": form.title.data,
            "description": form.description.data,
            "price": float(form.price.data),
            "published_at": form.published_at.data.strftime('%Y-%m-%d %H:%M:%S')
        }

        # 处理封面图片上传（存入 MongoDB）
        if form.cover.data:
            cover_file = form.cover.data
            cover_binary = cover_file.read()  # 直接读取二进制数据
            update_data["cover"] = cover_binary

        # 处理 PDF 云盘链接（不再上传文件）
        if form.pdf_link.data:
            update_data["pdf_link"] = form.pdf_link.data  # 存储云盘链接

        # 执行更新操作
        response = current_app.db.table("books").update(update_data).eq("id", book_id).execute()

        flash("书籍信息更新成功！", "success")
        return redirect(url_for('auth.dashboard'))

    return render_template("edit.html", form=form, book=book, title="编辑书籍")

@auth_bp.route('/delete/<book_id>', methods=['POST'])
@login_required
def delete(book_id):
    # 删除 ID 对应的书籍
    response = current_app.db.table("books").delete().eq("id", book_id).execute()
    flash("书籍删除成功！", "success")
    return redirect(url_for('auth.dashboard'))


@auth_bp.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    if request.method == 'POST':
        referral_code = request.form.get('referral_code')
        wallet_address = request.form.get('wallet_address')
        amount = float(request.form.get('amount'))  # 手动录入提现金额
        total_balance = get_user_balance(referral_code)  # 查询推荐者剩余金额
        remaining_balance = total_balance - amount  # 自动计算剩余金额

        # 插入提现记录
        withdraw_record = {
            "referral_code": referral_code,
            "wallet_address": wallet_address,
            "amount": amount,
            "remaining_balance": remaining_balance,
            "transaction_time": datetime.datetime.utcnow()
        }

        current_app.db.withdrawals.insert_one(withdraw_record)
        flash("提现记录添加成功！", "success")
        return redirect(url_for('auth.withdraw'))

    # 获取所有提现记录
    withdraws = list(current_app.db.withdrawals.find({}, {"_id": 0}))
    return render_template("withdraw.html", withdraws=withdraws)

def get_user_balance(referral_code):
    """模拟一个查询推荐者钱包余额的函数"""
    user = current_app.db.users.find_one({"referral_code": referral_code}, {"balance": 1, "_id": 0})
    return user["balance"] if user else 0
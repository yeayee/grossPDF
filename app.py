import os
from flask import Blueprint, jsonify, request, redirect, url_for, render_template, flash, current_app, send_file

from flask_bootstrap import Bootstrap
from auth.routes import auth_bp

from config import create_app
app = create_app()
app_static_folder = os.path.abspath(app.static_folder)

from bson import ObjectId


from wtforms import StringField, HiddenField, SubmitField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm
from wtforms import SubmitField
import time
import base64
from flask import abort, send_from_directory
import random
import string
import requests

contact_me = {'id': 5,"title": "Contact Me", 
              "cover": "https://github.com/yeayee/yeayee/raw/main/%E5%BE%AE%E4%BF%A1%E5%9B%BE%E7%89%87_20240731085559.jpg"}
  


# Coinbase Commerce API 相关配置

COINBASE_API_KEY = "cdd70848-e3be-4e8e-af03-75a5e43c166a"

COINBASE_API_URL = "https://api.commerce.coinbase.com/charges"

def generate_random_code(k):
    characters = string.ascii_letters + string.digits  # 包含大小写字母和数字
    return ''.join(random.choices(characters, k=k))
    
@app.route('/')
def home():
    # 获取所有书籍
    response = current_app.db.table("books").select("*").execute()

    # 转换为列表
    books = response.data if response.data else [] 
    return render_template('index.html', books=books,contact_me=contact_me)

@app.route('/search')
def search():
    query = request.args.get('query', '').strip()  # 获取搜索关键词，并去除空格
    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400

    response = current_app.db.table("books").select("*").ilike("title", f"%{query}%").execute()

    books = response.data if response.data else []


    if not books:
        return jsonify({"error": "No matching books found"}), 404  # More accurate error message

 
    # print(books)
    return render_template('index.html', books=books,contact_me=contact_me)

class PaymentForm(FlaskForm):
    order_number = StringField("支付参考号", validators=[DataRequired()])
    book_id = HiddenField("书籍ID")
    submit = SubmitField("提取PDF")

# 生成推荐码
@app.route('/book_detail/<id>')  
def generate_referral(id):
    referral_code = generate_random_code(8)
    return redirect(url_for('book_detail', id=id, referral_code=referral_code))

@app.route('/book_detail/<id>/<referral_code>')  # 这里改成字符串参数
def book_detail(id, referral_code):
    form = PaymentForm()
    form.book_id.data = id  # 这里给 HiddenField 赋值
    # 查询 ID 对应的书籍
    response = current_app.db.table("books").select("*").eq("id", id).execute()

    # 提取数据
    book = response.data[0] if response.data else None
    if not book:
        flash("The book does not exist！", "danger")
        return redirect(url_for('auth.dashboard'))
    book["cover_base64"] = base64.b64encode(book["cover"]).decode("utf-8")
    order_number = generate_random_code(8)
    name = book["title"]
    amount = book["price"]
    headers = {
        "Content-Type": "application/json",  
        "X-CC-Api-Key": COINBASE_API_KEY
    }
    payment_data = {
        "name": name,
        "description": order_number,
        "pricing_type": "fixed_price",
        "local_price": {"amount": amount, "currency": "USD"},
        "metadata": {"referral_code": referral_code,"order_number":order_number,"book_id":id}
    }
    response = requests.post(COINBASE_API_URL, json=payment_data, headers=headers)
    payment_url = response.json().get("data", {}).get("hosted_url")
    # 随机码
    response = current_app.db.table("books").select("*").limit(1).execute()

    # 提取数据
    book_01 = response.data[0] if response.data else None
    random_str = book_01.get("description")[:4]
    # 生成随机码
    keyword = request.args.get('res', 'wrong')
    if keyword == random_str:
        # 缺省推荐数据及其响应的前端模板
        query = {
            "event.data.metadata.referral_code": referral_code,
            "event.type": "charge:confirmed"
        }

        response = current_app.db.table("payment").select("event->data->wallet_address, event->data->local_price, event->data->created_at").match(query).execute()

        orders = response.data if response.data else []

        # 提取所需信息
        order_list = [
            {
                "wallet_prefix": order["event.data.wallet_address"][:8],  # 截取钱包地址前 8 位
                "amount": order["event.local_price.amount"],
                "transaction_time": order["event.data.transaction_time"]
            }
            for order in orders
        ]
        return render_template('orders.html', orders=order_list)
    return render_template("book_detail.html", book=book,form = form,order_number = order_number,
                           payment_url =payment_url,referral_code=referral_code,payment_data=False )

@app.route("/confirm_payment", methods=["POST"])
def confirm_payment():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON format"}), 400
    order_number = data.get("order_number")
    book_id = data.get("book_id")
    if not order_number or not book_id:
        return jsonify({"error": "Missing order number or book ID"}), 400
    # 在这里可以进行支付验证的逻辑
    # 在数据库中查询支付记录
    # 查询支付记录，确保订单号匹配且交易已确认
    response = current_app.db.table("payments").select("*").match({
        "event->data->metadata->order_number": order_number,
        "event->type": "charge:confirmed"
    }).execute()

    payment = response.data[0] if response.data else None

    if payment:
        # 获取当前提取次数，默认为 0
        attempts = payment.get("download_attempts", 0)

        if attempts < 3:
            # 获取 PDF 下载链接
            book_response = current_app.db.table("books").select("pdf_link").eq("id", book_id).execute()
            book = book_response.data[0] if book_response.data else None
            pdf_link = book.get("pdf_link") if book else None

            # 更新提取次数
            current_app.db.table("payments").update({"download_attempts": attempts + 1}).eq("id", payment["id"]).execute()

            return jsonify({"message": "Success", "download_url": pdf_link})
        else:
            return jsonify({"message": "Download limit exceeded", "download_url": None})
    else:
        return jsonify({"message": "Payment record not found", "download_url": None})

               
@app.route("/webhook", methods=["POST"])
def webhook():
    event = request.get_json(silent=True)  # 安全解析 JSON

    if event and event.get("event", {}).get("type") == "charge:confirmed":
        # 插入数据到 Supabase
        response = current_app.db.table("payments").insert({
            "event": event  # 直接存储整个事件 JSON
        }).execute()

        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "error"}), 400

    
if __name__ == '__main__':
    app.run(debug=True)

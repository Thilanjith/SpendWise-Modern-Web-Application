import os
from functools import wraps
from datetime import datetime
from decimal import Decimal
import mysql.connector
from mysql.connector import Error
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-me')
DB = dict(host=os.getenv('DB_HOST','localhost'), port=int(os.getenv('DB_PORT','3306')), user=os.getenv('DB_USER','root'), password=os.getenv('DB_PASSWORD',''), database=os.getenv('DB_NAME','spendwise'))

def db(): return mysql.connector.connect(**DB)
def run(sql,p=(),fetch=False):
    c=db(); cur=c.cursor(dictionary=True)
    try:
        cur.execute(sql,p)
        data=cur.fetchall() if fetch else cur.lastrowid
        c.commit(); return data
    finally: cur.close(); c.close()
def one(sql,p=()):
    r=run(sql,p,True); return r[0] if r else None
def auth(f):
    @wraps(f)
    def w(*a,**k):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*a,**k)
    return w
@app.context_processor
def globals_(): return {'current_user':session.get('user_name')}
@app.route('/')
def home(): return redirect(url_for('dashboard' if 'user_id' in session else 'login'))
@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form['name'].strip(); email=request.form['email'].strip().lower(); pw=request.form['password']; cp=request.form['confirm_password']
        if not name or not email or len(pw)<6 or pw!=cp: flash('Check your details and make sure passwords match (6+ characters).','danger'); return render_template('register.html')
        if one('SELECT user_id FROM users WHERE email=%s',(email,)): flash('Email already registered.','warning'); return render_template('register.html')
        run('INSERT INTO users(name,email,password) VALUES(%s,%s,%s)',(name,email,generate_password_hash(pw))); flash('Account created.','success'); return redirect(url_for('login'))
    return render_template('register.html')
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=one('SELECT * FROM users WHERE email=%s',(request.form['email'].strip().lower(),))
        if u and check_password_hash(u['password'],request.form['password']): session.update(user_id=u['user_id'],user_name=u['name'],user_email=u['email']); return redirect(url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/dashboard')
@auth
def dashboard():
    uid=session['user_id']; s=one("SELECT COALESCE(SUM(CASE WHEN transaction_type='Income' THEN amount ELSE 0 END),0) income, COALESCE(SUM(CASE WHEN transaction_type='Expense' THEN amount ELSE 0 END),0) expense FROM transactions WHERE user_id=%s",(uid,)); income=Decimal(str(s['income'])); expense=Decimal(str(s['expense']));
    recent=run("SELECT t.*,c.category_name FROM transactions t JOIN categories c ON t.category_id=c.category_id WHERE t.user_id=%s ORDER BY transaction_date DESC,transaction_id DESC LIMIT 8",(uid,),True)
    cats=run("SELECT c.category_name,SUM(t.amount) total FROM transactions t JOIN categories c ON t.category_id=c.category_id WHERE t.user_id=%s AND t.transaction_type='Expense' GROUP BY c.category_id,c.category_name ORDER BY total DESC LIMIT 6",(uid,),True)
    monthly=run("SELECT DATE_FORMAT(transaction_date,'%Y-%m') month,SUM(CASE WHEN transaction_type='Income' THEN amount ELSE 0 END) income,SUM(CASE WHEN transaction_type='Expense' THEN amount ELSE 0 END) expense FROM transactions WHERE user_id=%s GROUP BY month ORDER BY month DESC LIMIT 6",(uid,),True); monthly.reverse()
    return render_template('dashboard.html',income=income,expense=expense,balance=income-expense,recent=recent,cats=cats,monthly=monthly)
@app.route('/transactions',methods=['GET','POST'])
@auth
def transactions():
    uid=session['user_id']
    if request.method=='POST':
        tid=request.form.get('transaction_id'); typ=request.form['transaction_type']; cid=request.form['category_id']; amount=Decimal(request.form['amount']); date=request.form['transaction_date']; desc=request.form.get('description','').strip()
        if tid: run('UPDATE transactions SET category_id=%s,amount=%s,transaction_type=%s,description=%s,transaction_date=%s WHERE transaction_id=%s AND user_id=%s',(cid,amount,typ,desc,date,tid,uid)); flash('Transaction updated.','success')
        else: run('INSERT INTO transactions(user_id,category_id,amount,transaction_type,description,transaction_date) VALUES(%s,%s,%s,%s,%s,%s)',(uid,cid,amount,typ,desc,date)); flash('Transaction added.','success')
        return redirect(url_for('transactions'))
    rows=run('SELECT t.*,c.category_name FROM transactions t JOIN categories c ON t.category_id=c.category_id WHERE t.user_id=%s ORDER BY transaction_date DESC,transaction_id DESC',(uid,),True)
    cats=run('SELECT category_id,category_name,category_type FROM categories WHERE user_id=%s ORDER BY category_type,category_name',(uid,),True)
    return render_template('transactions.html',transactions=rows,categories=cats,today=datetime.now().strftime('%Y-%m-%d'))
@app.post('/transactions/delete/<int:tid>')
@auth
def deltx(tid): run('DELETE FROM transactions WHERE transaction_id=%s AND user_id=%s',(tid,session['user_id'])); flash('Transaction deleted.','success'); return redirect(url_for('transactions'))
@app.route('/categories',methods=['GET','POST'])
@auth
def categories():
    uid=session['user_id']
    if request.method=='POST':
        cid=request.form.get('category_id'); name=request.form['category_name'].strip(); typ=request.form['category_type']
        try:
            if cid: run('UPDATE categories SET category_name=%s,category_type=%s WHERE category_id=%s AND user_id=%s',(name,typ,cid,uid))
            else: run('INSERT INTO categories(user_id,category_name,category_type) VALUES(%s,%s,%s)',(uid,name,typ))
            flash('Category saved.','success')
        except Error: flash('Category already exists or cannot be changed.','warning')
        return redirect(url_for('categories'))
    rows=run('SELECT c.*,COUNT(t.transaction_id) transaction_count FROM categories c LEFT JOIN transactions t ON c.category_id=t.category_id WHERE c.user_id=%s GROUP BY c.category_id ORDER BY c.category_type,c.category_name',(uid,),True); return render_template('categories.html',categories=rows)
@app.post('/categories/delete/<int:cid>')
@auth
def delcat(cid):
    try: run('DELETE FROM categories WHERE category_id=%s AND user_id=%s',(cid,session['user_id'])); flash('Category deleted.','success')
    except Error: flash('Delete its transactions first.','warning')
    return redirect(url_for('categories'))
if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=True)

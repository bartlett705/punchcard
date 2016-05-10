#!venv/bin/python

import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
from contextlib import closing
from decimal import *
from time import strftime, localtime

#configuration
DATABASE = '/tmp/punch-card.db'
DEBUG = True
SECRET_KEY = 'one_tagger'
USERNAME = 'lance'
PASSWORD = 'themostvaluableresourc3'

# open a connection to the datbase using sqlite3
def connect_db():
	return sqlite3.connect(app.config['DATABASE'])

# initialize the database using schema
def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

#dat app
app = Flask(__name__)
app.config.from_object(__name__)

# initialize database connections before each request
@app.before_request
def before_request():
	g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
	db = getattr(g, 'db', None)
	if db is not None:
		db.close()

# define views.
# first view - show_entries
@app.route('/')
def show_entries():
	getcontext().prec = 2 # set precision for decimal representation of hours worked.
	cur = g.db.execute('select in_time, out_time, desc from entries order by in_time asc') # sort by ascending in time
	entries = [dict(in_time=strftime("%a, %d %b %Y %H:%M:%S", localtime(rows[0])), out_time=strftime("%a, %d %b %Y %H:%M:%S", localtime(rows[1])), elapsed=Decimal((rows[1] - rows[0])/Decimal(3600)), desc=rows[2]) for rows in cur.fetchall()] # list comprehension creating a dictionary of entries out of the tuples returned by the cursor fetch (data in tuples is in the same order as the select query)
	total_time = 0
	for i_dx in range(len(entries)):
		total_time += entries[i_dx]['elapsed']
	return render_template('show_entries.html', entries=entries, total_time=total_time) # pass the dict to show_entries.html and render the template

# second view - post new entry
@app.route('/post', methods=['POST'])
def post_entry():
	if not session.get('logged_in'): # check if the logged_in key is present in the session
		abort(401)
	g.db.execute('insert into entries (in_time, out_time, desc) values (?, ?, ?)', [request.form['inTime'], request.form['outTime'], request.form['desc']])
	g.db.commit()
	flash('DATABASE TRANSMISSION COMMIT : SUCCESS')
	return redirect(url_for('show_entries'))

@app.route('/login', methods=['GET', 'POST'])
def login():
	error = None
	if request.method == 'POST':
		if request.form['username'] != app.config['USERNAME']:
			error = 'NAME CREDENTIAL FAILURE'
		elif request.form['password'] != app.config['PASSWORD']:
			error = 'SECURITY CREDENTIAL FAILURE'
		else:
			session['logged_in'] = True
			flash('CREDIENTIALS VERIFIED')
			return redirect(url_for('show_entries'))
	return render_template('login.html', error=error)

@app.route('/logout')
def logout():
	session.pop('logged_in')
	flash('SECURE SESSION TERMINATED')
	return redirect(url_for('show_entries'))

if __name__ == '__main__':
	app.run()

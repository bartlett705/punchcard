#!venv/bin/python

import sqlite3
import os, sys
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
from contextlib import closing
from decimal import *
from time import strftime, localtime
import re
from flipflop import WSGIServer

sys.path.append(os.path.dirname(__file__))
sys.path.append("/var/www/punchcard/venv/lib/python2.7/site-packages")
# super-secure configuration

DATABASE = '/var/www/punchcard/punch-card.db'
SECRET_KEY = 'one_tagger'
USERNAME = 'lance'
PASSWORD = 'themostvaluableresourc3'
tag_link_markup = r'<a href="/pc/tags/\1" class="tag-link">\1</a>'
date_link_markup = r'<a href="/pc/\2/\1" class="date-link">\1 \2</a>'


# helpers
def link_up_entry(entry):
    # type: (dict) -> dict
    entry['desc'] = re.sub(r'\[(\w+)\]', tag_link_markup, entry['desc'])
    entry['in_time'] = re.sub(r'([a-zA-Z]{3})\s(\d{4})', date_link_markup, entry['in_time'])
    entry['out_time'] = re.sub(r'([a-zA-Z]{3})\s(\d{4})', date_link_markup, entry['out_time'])


# open a connection to the database using sqlite3
def connect_db():
    return sqlite3.connect(application.config['DATABASE'])


# initialize the database using schema
def init_db():
    with closing(connect_db()) as db:
        with application.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


# dat application
application = Flask(__name__)
application.config.from_object(__name__)


# initialize database connections before each request
@application.before_request
def before_request():
    g.db = connect_db()


@application.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if exception:
        flash(exception)
    if db is not None:
        db.close()


# define views.
# first view - show_entries
@application.route('/')
def show_all_entries():
    getcontext().prec = 2  # set precision for decimal representation of hours worked.
    cur = g.db.execute('select in_time, out_time, desc from entries order by in_time asc')  # sort by ascending in time
    entries = [dict(in_time=strftime("%a, %d %b %Y %H:%M:%S", localtime(rows[0])),
                    out_time=strftime("%a, %d %b %Y %H:%M:%S", localtime(rows[1])),
                    elapsed=Decimal((rows[1] - rows[0]) / Decimal(3600)), desc=rows[2]) for rows in
               cur.fetchall()]
    # list comprehension creating a list of dictionaries, each containing one of the tuples
    # returned by the cursor fetch (data in tuples is in the same order as the select query)
    for entry in entries:  # link up tags
        link_up_entry(entry)
    total_time = 0
    for i_dx in range(len(entries)):
        total_time += entries[i_dx]['elapsed']
    return render_template('show_entries.html', entries=entries,
                           total_time=total_time)  # pass the dict to show_entries.html and render the template


@application.route('/tags/<search_tag>')
def show_tagged_entries(search_tag):
    getcontext().prec = 2  # set precision for decimal representation of hours worked.
    cur = g.db.execute('select in_time, out_time, desc from entries order by in_time asc')  # sort by ascending in time
    all_entries = [dict(in_time=strftime("%a, %d %b %Y %H:%M:%S", localtime(rows[0])),
                        out_time=strftime("%a, %d %b %Y %H:%M:%S", localtime(rows[1])),
                        elapsed=Decimal((rows[1] - rows[0]) / Decimal(3600)), desc=rows[2]) for rows in cur.fetchall()]
    # delete all the entries that don't contain the desired tag.
    tagged_entries = []
    for entry in all_entries:
        found_tags = re.findall('\[(\w+)\]', entry['desc'])
        found_tags = [tag.lower() for tag in found_tags]
        if search_tag.lower() in found_tags:
            link_up_entry(entry)
            tagged_entries.append(entry)
    total_time = 0
    for i_dx in range(len(tagged_entries)):
        total_time += tagged_entries[i_dx]['elapsed']
    return render_template('show_entries.html', entries=tagged_entries, total_time=total_time,
                           search_tag=search_tag)  # pass the dict to show_entries.html and render the template


@application.route('/<year>/<month>')
def show_month_entries(year, month):
    getcontext().prec = 2  # set precision for decimal representation of hours worked.
    cur = g.db.execute('select in_time, out_time, desc from entries order by in_time asc')  # sort by ascending in time
    all_entries = [dict(in_time=strftime("%a, %d %b %Y %H:%M:%S", localtime(rows[0])),
                        out_time=strftime("%a, %d %b %Y %H:%M:%S", localtime(rows[1])),
                        elapsed=Decimal((rows[1] - rows[0]) / Decimal(3600)), desc=rows[2]) for rows in cur.fetchall()]
    # delete all the entries that don't contain the desired tag.
    month_entries = []
    for entry in all_entries:
        in_time_search = re.search(r'([a-zA-Z]{3})\s(\d{4})', entry['in_time'])
        out_time_search = re.search(r'([a-zA-Z]{3})\s(\d{4})', entry['out_time'])
        if (in_time_search.group(2) == year and month.lower() == in_time_search.group(1).lower()) or (
                out_time_search.group(2) == year and month.lower() == out_time_search.group(1).lower()):
            link_up_entry(entry)
            month_entries.append(entry)
    total_time = 0
    for i_dx in range(len(month_entries)):
        total_time += month_entries[i_dx]['elapsed']
    return render_template('show_entries.html', entries=month_entries, total_time=total_time, year=year,
                           month=month)  # pass the dict to show_entries.html and render the template


# second view - post new entry
@application.route('/post', methods=['POST'])
def post_entry():
    if not session.get('logged_in'):  # check if the logged_in key is present in the session
        abort(401)
    if request.form['inTime'] and request.form['outTime']:
        g.db.execute('insert into entries (in_time, out_time, desc) values (?, ?, ?)', [request.form['inTime'], request.form['outTime'], request.form['desc']])
        g.db.commit()
        flash('DATABASE TRANSMISSION COMMIT : SUCCESS')
        return redirect(url_for('show_all_entries'))
    else:
        flash('MISSING DATA DISALLOWED - TRY AGAIN.')
        return redirect(url_for('show_all_entries'))


@application.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != application.config['USERNAME']:
            error = 'NAME CREDENTIAL FAILURE'
        elif request.form['password'] != application.config['PASSWORD']:
            error = 'SECURITY CREDENTIAL FAILURE'
        else:
            session['logged_in'] = True
            flash('CREDIENTIALS VERIFIED')
            return redirect(url_for('show_all_entries'))
    return render_template('login.html', error=error)


@application.route('/logout')
def logout():
    session.pop('logged_in')
    flash('SECURE SESSION TERMINATED')
    return redirect(url_for('show_all_entries'))


if __name__ == '__main__':
    WSGIServer(application).run(debug=True)

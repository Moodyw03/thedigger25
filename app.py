from flask import Flask, abort
from markupsafe import escape

app = Flask(__name__)

app.debug = True


@app.route('/')
@app.route('/index/')
def hello():
    return '&lt;div&gt;This is a div element&lt;/div&gt;'


@app.route('/about/')
def about():
    return '<h3>This is a Flask web application.</h3>'

@app.route('/capitalize/<word>/')
def capitalize(word):
    print(escape(word.capitalize()))
    return '<h1>{}</h1>'.format(escape(word.capitalize()))


@app.route('/add/<int:n1>/<int:n2>/')
def add(n1, n2):
    return '<h1>{}</h1>'.format(n1 + n2)


# ...

@app.route('/users/<int:user_id>/')
def greet_user(user_id):
    users = ['Bob', 'Jane', 'Adam']
    try:
        return '<h2>Hi {}</h2>'.format(users[user_id])
    except IndexError:
        abort(404)


if __name__ == '__main__':
    app.run(use_reloader=True)

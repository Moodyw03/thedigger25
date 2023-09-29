from flask import Flask, jsonify, request
from main import main


app = Flask(__name__)

app.debug = True

@app.route('/api/list', methods=['GET'])
def fetch_artists():
    # Access the 'artist_name' query parameter
    artist_name = request.args.get('artist_name', 'Ben UFO')
    arrays = main(artist_name)

    # Use jsonify to return the array of arrays as JSON
    return jsonify(arrays)


if __name__ == '__main__':
    app.run(use_reloader=True)

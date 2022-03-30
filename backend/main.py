import io
import os

import requests as requests
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from plex.classes import PlexWrapper

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///movies.db"
db = SQLAlchemy(app)
CORS(app)

# Create db model
class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    media_id = db.Column(db.Integer, nullable=False)
    media_name = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return "<Name %r>" % self.id


@app.errorhandler(Exception)
def internal_error(error):
    return jsonify({"error": str(error)}), 500


@app.route("/server/info")
def get_server_info():
    info = PlexWrapper().get_server_info()
    return jsonify(info)


@app.route("/server/proxy")
def get_server_proxy():
    # Proxy a request to the server - useful when the user
    # is viewing the cleanarr dash over HTTPS to avoid the browser
    # blocking untrusted server certs
    url = request.args.get("url")
    r = requests.get(url)
    return send_file(io.BytesIO(r.content), mimetype="image/jpeg")


@app.route("/content/dupes")
def get_movies():
    ignored_files_count = db.session.query(Media).count()
    duplicated_movies = PlexWrapper().get_dupe_content(ignored_files_count=ignored_files_count)
    duplicated_files = []

    for movie in duplicated_movies:

        dupes_media = [
            media
            for media in movie["media"]
            if not bool(db.session.query(Media).filter_by(media_id=media["id"]).first())
        ]
        movie["media"] = dupes_media

        if len(dupes_media) > 1:
            duplicated_files += [movie]

    print(duplicated_files)
    return jsonify(duplicated_files)


@app.route("/content/samples")
def get_movies_samples():
    samples = PlexWrapper().get_content_sample_files()
    return jsonify(samples)


@app.route("/delete/media", methods=["POST"])
def delete_media():
    content = request.get_json()
    content_key = content["content_key"]
    media_id = content["media_id"]

    content = PlexWrapper().get_content(content_key)

    for media in content.media:
        if media.id == media_id:
            print(content.title, media.id)
            for part in media.parts:
                print(part.file)
            media.delete()
    return jsonify({"success": True})


@app.route("/ignore/media", methods=["POST"])
def ignore_media():
    content = request.get_json()
    content_key = content["content_key"]
    media_id = content["media_id"]

    content = PlexWrapper().get_content(content_key)

    with open("ignore.txt", "a") as the_file:
        try:
            if db.session.query(Media).filter_by(media_id=media_id).count() < 1:
                db.session.add(Media(media_id=media_id, media_name=content.title))
                db.session.commit()
        except:
            pass

    return jsonify({"success": True})

    # for media in content.media:
    #     if media.id == media_id:
    #         print(content.title, media.id)
    #         for part in media.parts:
    #             print(part.file)
    #         media.delete()
    # return jsonify({"success": True})


# Static File Hosting Hack
# See https://github.com/tiangolo/uwsgi-nginx-flask-docker/blob/master/deprecated-single-page-apps-in-same-container.md
@app.route("/")
def main():
    index_path = os.path.join(app.static_folder, "index.html")
    return send_file(index_path)


# Everything not declared before (not a Flask route / API endpoint)...
@app.route("/<path:path>")
def route_frontend(path):
    # ...could be a static file needed by the front end that
    # doesn't use the `static` path (like in `<script src="bundle.js">`)
    file_path = os.path.join(app.static_folder, path)
    if os.path.isfile(file_path):
        return send_file(file_path)
    # ...or should be handled by the SPA's "router" in front end
    else:
        index_path = os.path.join(app.static_folder, "index.html")
        return send_file(index_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

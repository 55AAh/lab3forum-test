from urllib import parse
from flask import Flask, render_template, redirect, make_response, request, abort
import os
from server import Server

app = Flask("Lab3Forum")
server = None


@app.before_first_request
def init():
    global server
    server = Server()


class RequestData:
    def __init__(self):
        self.logged_in = False
        self.username, self.password = None, None

    @staticmethod
    def quote(val):
        if val is None:
            return None
        return parse.quote(val)

    @staticmethod
    def unquote(val):
        if val is None:
            return None
        return parse.unquote(val)

    def parse(self, dictionary):
        for key, value in dictionary.items():
            value = RequestData.unquote(value)
            if value == "null":
                value = None
            self.__dict__[key] = value
        if "logged_in" in self.__dict__ and str(self.logged_in).lower() == "true":
            self.logged_in = server.auth_user(self.username, self.password)
        else:
            self.logged_in = False
        return self

    def form(self, require_auth_params=False):
        if require_auth_params:
            if "username" not in request.form or "password" not in request.form:
                return None
        return self.parse(request.form)

    def cookies(self):
        return self.parse(request.cookies)

    def save_cookies(self, response=None):
        if response is None:
            response = make_response()
        for key, value in self.__dict__.items():
            response.set_cookie(key, RequestData.quote(str(value)))
        return response

    def delete_cookies(self, response=None):
        if response is None:
            response = make_response()
        for key in self.__dict__:
            response.delete_cookie(key)
        return response


@app.route("/threads")
def threads_list():
    req_data = RequestData().cookies()
    users_count, threads_count, comments_count = server.get_stats()
    html = ""
    for thread in server.get_threads_list():
        creator_username = thread.creator.username
        if thread.creator.username == req_data.username:
            creator_username = "<b>" + creator_username + "</b>"
        html += render_template("thread-preview.html",
                                creator_username=creator_username,
                                thread=thread) + "\n"
    return render_template("threads-list.html",
                           **req_data.__dict__,
                           users_count=users_count, threads_count=threads_count, comments_count=comments_count,
                           threads_html=html)


@app.route("/threads/<thread_id>")
def thread(thread_id):
    try:
        thread_id = int(thread_id)
    except ValueError:
        abort(400)
    req_data = RequestData().cookies()
    thread = server.get_thread(thread_id)
    if thread is None:
        return redirect("/threads")
    comments = list()
    comments_map = dict()
    for cmt in server.get_thread_comments(thread_id):
        cmt.replies = list()
        if cmt.reply_id is None:
            comments.append(cmt)
        else:
            comments_map[cmt.reply_id].replies.append(cmt)
        comments_map[cmt.id] = cmt

    def rec(base, depth_ind=0):
        html = ""
        for cmt in base:
            replies_html = rec(cmt.replies, depth_ind + 1)
            author_username = cmt.author.username
            if cmt.author.username == req_data.username:
                author_username = "<b>" + author_username + "</b>"
            if cmt.author.username == thread.creator.username:
                author_username = '<span style="background: cornsilk">' + author_username + "</span>"
            html += render_template("comment.html",
                                    **req_data.__dict__,
                                    cmt=cmt,
                                    author_username=author_username,
                                    depth_ind=depth_ind,
                                    collapse_text=("Collapse" if replies_html != "" else ""),
                                    replies_html=replies_html) + "\n"
        return html

    comments_html = rec(comments)
    return render_template("thread.html",
                           **req_data.__dict__,
                           thread=thread,
                           is_owner=thread.creator.username == req_data.username,
                           comments_html=comments_html)


@app.route("/register")
def register():
    req_data = RequestData().cookies()
    return render_template("register.html",
                           **req_data.__dict__)


@app.route("/new-thread")
def new_thread():
    req_data = RequestData().cookies()
    if not req_data.logged_in:
        abort(403)
    return render_template("new-thread.html",
                           **req_data.__dict__)


@app.route("/admin")
def admin_panel():
    return render_template("admin-panel.html",
                           admin_password=server.get_admin_password())


@app.route("/api/login", methods=["POST"])
def api_login():
    req_data = RequestData().form(require_auth_params=True)
    if req_data is None:
        abort(400)
    if not req_data.logged_in:
        abort(403)
    return req_data.save_cookies()


@app.route("/api/logout", methods=["POST"])
def api_logout():
    req_data = RequestData().form()
    return req_data.delete_cookies()


@app.route("/api/register_check_free", methods=["POST"])
def api_register_check_free():
    req_data = RequestData().form()
    if "username" not in req_data.__dict__:
        abort(400)
    if not server.check_free_username(req_data.username):
        abort(403)
    return ""


@app.route("/api/register", methods=["POST"])
def api_register():
    req_data = RequestData().form(require_auth_params=True)
    if req_data is None:
        abort(400)
    if req_data.logged_in:
        return ""
    new_user = server.register_user(req_data.username, req_data.password)
    if new_user is None:
        abort(403)
    req_data.logged_in = True
    return req_data.save_cookies()


@app.route("/api/new-thread", methods=["POST"])
def api_new_thread():
    req_data = RequestData().form(require_auth_params=True)
    if req_data is None or "title" not in req_data.__dict__ or "text" not in req_data.__dict__:
        abort(400)
    if not req_data.logged_in:
        abort(403)
    new_thread = server.create_thread(req_data.username, req_data.title, req_data.text)
    if new_thread is None:
        abort(403)
    return str(new_thread.id)


@app.route("/api/send-comment", methods=["POST"])
def api_send_comment():
    req_data = RequestData().form(require_auth_params=True)
    if req_data is None \
            or "thread_id" not in req_data.__dict__ \
            or "reply_id" not in req_data.__dict__ \
            or "text" not in req_data.__dict__:
        abort(400)
    if not req_data.logged_in:
        abort(403)
    new_comment = server.add_comment(req_data.thread_id, req_data.username, req_data.reply_id, req_data.text)
    if new_comment is None:
        abort(403)
    return str(new_comment.id)


@app.route("/api/delete-thread", methods=["POST"])
def api_delete_thread():
    req_data = RequestData().form(require_auth_params=True)
    if req_data is None \
            or "thread_id" not in req_data.__dict__:
        abort(400)
    if not req_data.logged_in:
        abort(403)
    thread = server.get_thread(req_data.thread_id)
    if thread.creator.username != req_data.username:
        abort(403)
    return server.delete_thread(req_data.thread_id)


@app.route("/api/reset-database", methods=["POST"])
def api_reset_database():
    req_data = RequestData().form()
    if "admin_password" not in req_data.__dict__:
        abort(400)
    if req_data.admin_password != server.get_admin_password():
        abort(403)
    server.reset_database()
    return ""


@app.route("/")
def index():
    return redirect("/threads")


if __name__ == "__main__":
    if os.environ.get("DEBUG"):
        app.jinja_env.auto_reload = True
        app.config['TEMPLATES_AUTO_RELOAD'] = True
        app.debug = True
    host = os.environ.get("HOST", '127.0.0.1')
    port = int(os.environ.get("PORT", 80))
    app.run(host=host, port=port)

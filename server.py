from datetime import datetime, timedelta
from sqlalchemy import desc
from os import environ
from db import *


class Server:
    def __init__(self):
        self.admin_password = environ.get("ADMIN_PASSWORD")
        self.db = Db(environ.get("DATABASE_URL"), environ.get("DEBUG"))
        if self.db.is_empty():
            self.reset_database()

    def auth_user(self, username, password):
        user = User.find(self.db.session(), username)
        if user is None:
            return None
        return password == user.authkey

    def get_stats(self):
        users_count = self.db.session().query(User).count()
        threads_count = self.db.session().query(Thread).count()
        comments_count = self.db.session().query(Comment).count()
        return users_count, threads_count, comments_count

    def get_threads_list(self):
        return self.db.session().query(Thread).order_by(desc(Thread.lasttime)).all()

    def get_thread(self, id):
        return self.db.session().query(Thread).filter(Thread.id == id).first()

    def get_thread_comments(self, thread_id):
        return self.db.session().query(Comment).filter(Comment.thread_id == thread_id).order_by(Comment.id).all()

    def check_free_username(self, username):
        if username == "":
            return None
        return User.find(self.db.session(), username) is None

    def register_user(self, username, password):
        if username == "" or password == "":
            return None
        with self.db.session as session:
            return User.new(session, username, password)

    def create_thread(self, username, title, text):
        if title == "":
            return None
        with self.db.session as session:
            user = User.find(session, username)
            if user is None:
                return None
            return Thread.new(session, user, title, text)

    def add_comment(self, thread_id, author_username, reply_id, text):
        if text == "":
            return None
        with self.db.session as session:
            thread = Thread.find(session, thread_id)
            if thread is None:
                return None
            author = User.find(session, author_username)
            if author is None:
                return None
            reply = None
            if reply_id is not None:
                reply = Comment.find(session, reply_id)
                if reply is None:
                    return None
            return Comment.new(session, thread, author, reply, text)

    def delete_thread(self, thread_id):
        with self.db.session as session:
            thread = Thread.find(session, thread_id)
            if thread is not None:
                thread.delete(session)
            return ""

    def get_admin_password(self):
        return self.admin_password

    def reset_database(self):
        self.db.session.session.close()
        Base.metadata.drop_all(self.db.engine)
        Base.metadata.create_all(self.db.engine)

        time = datetime(2021, 5, 9, 20, 0, 0)

        with self.db.session as session:
            user_alice = User.new(session, "alice", "alice_password")
            user_bob = User.new(session, "bob", "bob_password")

        with self.db.session as session:
            thread_math = Thread.new(session, user_alice, "Math", "Math-related discussions")

        with self.db.session as session:
            comment_math_1 = Comment.new(session, thread_math, user_alice, None, "I love math!")
            comment_math_2 = Comment.new(session, thread_math, user_alice, None, "Is anyone here?")
            comment_math_1.time = time
            time += timedelta(minutes=5)
            comment_math_2.time = time

        with self.db.session as session:
            comment_math_3 = Comment.new(session, thread_math, user_bob, comment_math_2, "I am.")
            time += timedelta(minutes=5)
            comment_math_3.time = time
            thread_math.lasttime = time

        with self.db.session as session:
            thread_arts = Thread.new(session, user_bob, "Arts", "Arts-related discussions")

        with self.db.session as session:
            comment_arts_1 = Comment.new(session, thread_arts, user_bob, None, "I love arts!")
            comment_arts_2 = Comment.new(session, thread_arts, user_bob, None, "Is anyone here?")
            time += timedelta(minutes=50)
            comment_arts_1.time = time
            time += timedelta(minutes=5)
            comment_arts_2.time = time

        with self.db.session as session:
            comment_arts_3 = Comment.new(session, thread_arts, user_alice, comment_arts_2, "I am.")
            time += timedelta(minutes=5)
            comment_arts_3.time = time
            thread_arts.lasttime = time

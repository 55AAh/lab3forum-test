from sqlalchemy import create_engine, Column, Integer, Sequence, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.engine.reflection import Inspector
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, Sequence("user_id_seq"), primary_key=True)
    username = Column(String, unique=True)
    authkey = Column(String, nullable=False)

    @staticmethod
    def new(session, username, password):
        unique = session.query(User.username).filter_by(username=username).first() is None
        if unique:
            new_user = User(username=username, authkey=password)
            session.add(new_user)
            return new_user
        return None

    @staticmethod
    def find(session, username):
        return session.query(User).filter_by(username=username).first()


class Thread(Base):
    __tablename__ = "threads"
    id = Column(Integer, Sequence("thread_id_seq"), primary_key=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    text = Column(String, nullable=False)
    lasttime = Column(DateTime, nullable=False)
    comments_count = Column(Integer, nullable=False, default=0)

    @staticmethod
    def new(session, creator, title, text):
        new_thread = Thread(creator_id=creator.id, title=title, text=text,
                            lasttime=datetime.now())
        session.add(new_thread)
        return new_thread

    @staticmethod
    def find(session, thread_id):
        return session.query(Thread).filter_by(id=thread_id).first()

    def delete(self, session):
        session.query(Comment).filter(Comment.thread_id == self.id).delete()
        session.query(Thread).filter(Thread.id == self.id).delete()


Thread.creator = relationship("User", back_populates="threads")
User.threads = relationship("Thread", order_by=Thread.lasttime, back_populates="creator")


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, Sequence("comment_id_seq"), primary_key=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reply_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    time = Column(DateTime, nullable=False)
    text = Column(String, nullable=False)

    @staticmethod
    def new(session, thread, author, reply, text):
        time = datetime.now()
        reply_id = reply.id if reply is not None else None
        new_comment = Comment(thread_id=thread.id, author_id=author.id, reply_id=reply_id,
                              time=time, text=text)
        session.add(new_comment)
        thread = session.query(Thread).filter(Thread.id == thread.id).first()
        thread.comments_count += 1
        thread.lasttime = time
        return new_comment

    @staticmethod
    def find(session, comment_id):
        return session.query(Comment).filter_by(id=comment_id).first()


Comment.author = relationship("User", back_populates="comments")
User.comments = relationship("Comment", order_by=Comment.id, back_populates="author")


Comment.thread = relationship("Thread", back_populates="comments")
Thread.comments = relationship("Comment", order_by=Comment.id, back_populates="thread")


class DbSession:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __call__(self, *args, **kwargs):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.commit()


class Db:
    def is_empty(self):
        return "users" not in self.inspector.get_table_names()

    @staticmethod
    def get_url_from_parameter(database_url):
        if database_url is None:
            return None
        return database_url.replace("postgres", "postgresql")

    @staticmethod
    def get_url_from_flyway():
        config = dict()
        with open("flyway.conf") as f:
            for line in f.readlines():
                if "=" in line:
                    key, value = line.split("=")
                    config[key] = value.strip()
        driver_dialect, address = config["flyway.url"].split("//")
        driver = driver_dialect.split(":")[1]
        user = config["flyway.user"]
        password = config["flyway.password"]
        return f'{driver}://{user}:{password}@{address}'

    def __init__(self, database_url, debug=False):
        debug = debug is not None
        database_url = Db.get_url_from_parameter(database_url)
        if database_url is None:
            database_url = Db.get_url_from_flyway()
        self.engine = create_engine(database_url, echo=debug)
        self.inspector = Inspector.from_engine(self.engine)
        self.session = DbSession(sessionmaker(bind=self.engine, expire_on_commit=False)())

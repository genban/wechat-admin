# coding=utf8

import datetime
import settings
from flask import request, Flask

from flask.ext.sqlalchemy import SQLAlchemy

from wechat_sdk import WechatBasic
from wechat_sdk.messages import EventMessage

from adapters.menu import WechatMenuAdapter
from adapters.qrcode import WechatQrcodeAdapter


app = Flask(__name__)
db_str = 'mysql://%s:%s@%s:%s/%s' % (
    settings.db_username,
    settings.db_password,
    settings.db_hostname,
    settings.db_port,
    settings.db_name)

db_binds = {
    settings.db_name: db_str,
}

app.config['TOKEN'] = settings.token
app.config['SQLALCHEMY_DATABASE_URI'] = db_str
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SQLALCHEMY_BINDS'] = db_binds

db = SQLAlchemy(app)


# models
class Qrcode(db.Model):

    __bind_key__ = 'wechat_admin'
    __tablename__ = 'qrcode'

    id = db.Column(db.Integer, primary_key=True)
    scene = db.Column(db.String(64), unique=True, index=True)
    ticket = db.Column(db.String(128))
    url = db.Column(db.String(128))
    path = db.Column(db.String(128))
    hash_key = db.Column(db.String(128))

    @classmethod
    def create_code(cls, name, ticket, url, path, hash_key):
        code = cls()
        code.scene = name
        code.ticket = ticket
        code.url = url
        code.path = path
        code.hash_key = hash_key
        db.session.add(code)
        db.session.commit()
        return code


class SubscribeEvent(db.Model):

    __bind_key__ = 'wechat_admin'
    __tablename__ = 'subscribe_event'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), index=True)
    scene = db.Column(db.String(32), index=True)
    subscribed_at = db.Column(db.DateTime, index=True)

    @classmethod
    def create_event(cls, user_id, scene, subscribed_at):
        event = cls()
        event.user_id = user_id
        event.scene = scene
        event.subscribed_at = datetime.datetime.fromtimestamp(subscribed_at)
        db.session.add(event)
        db.session.commit()
        return event


class UnsubscribeEvent(db.Model):

    __bind_key__ = 'wechat_admin'
    __tablename__ = 'unsubscribe_event'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), index=True)
    unsubscribed_at = db.Column(db.DateTime, index=True)

    @classmethod
    def create_event(cls, user_id, unsubscribed_at):
        event = cls()
        event.user_id = user_id
        event.unsubscribed_at = datetime.datetime.fromtimestamp(unsubscribed_at)
        db.session.add(event)
        db.session.commit()
        return event


@app.route('/', methods=['POST', 'GET'])
def index():
    token = app.config['TOKEN']
    signature = request.args.get('signature', '')
    timestamp = request.args.get('timestamp', '')
    nonce = request.args.get('nonce', '')

    # 实例化 wechat
    wechat = WechatBasic(token=token)

    if not wechat.check_signature(signature=signature,
                                  timestamp=timestamp, nonce=nonce):
        return 'fail'

    # 对签名进行校验
    echostr = request.args.get('echostr')
    if echostr:
        return echostr

    wechat.parse_data(request.data)
    message = wechat.get_message()
    if message.type == 'text':
        response = wechat.response_text(content=settings.auto_replay_text)
    elif message.type == 'image':
        response = wechat.response_text(u'图片')
    elif isinstance(message, EventMessage):
        if message.type == 'subscribe':
            if message.key and message.ticket:
                scene = message.key.startswith('qrscene_') and message.key[8:] or 'default'
            else:
                scene = 'default'

            SubscribeEvent.create_event(message.source, scene, message.time)
            response = wechat.response_text(content=settings.greetings)

        elif message.type == 'unsubscribe':
            UnsubscribeEvent.create_event(message.source, message.time)
            # TODO
            response = ''
        elif message.type == 'scan':
            # TODO
            response = ''
        elif message.type == 'location':
            response = wechat.response_text(content=u'上报地理位置事件')
        elif message.type == 'click':
            content = settings.click_menu_text_mapper.get(message.key, u'未知')
            response = wechat.response_text(content=content)
        elif message.type == 'view':
            response = wechat.response_text(content=u'自定义菜单跳转链接事件')
        elif message.type == 'templatesendjobfinish':
            response = wechat.response_text(content=u'模板消息事件')
    else:
        response = wechat.response_text(u'未知')
    return response


# TODO: to post
@app.route('/menus', methods=['GET'])
def create_menu():
    message = WechatMenuAdapter.create_menu(settings.menu)
    return message


# TODO: to post
@app.route('/qrcodes', methods=['GET'])
def create_qrcode():
    name = request.args.get('name', '')
    url = WechatQrcodeAdapter.create_qrcode(name)
    return url


@app.route('/show_qrcodes', methods=['GET'])
def show_qrcode():
    ret = list(WechatQrcodeAdapter.show_all_qrcodes())
    return str(ret)


app.config['DEBUG'] = True
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=9998,)


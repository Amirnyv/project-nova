"""Session/CSRF adapters and single-host abuse limits for direct messaging."""
import fcntl
import hashlib
import hmac
import json
import time
from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user
from werkzeug.exceptions import RequestEntityTooLarge
from services.nova_chat import ChatError, DirectChat


class ChatRateLimiter:
    """Sliding windows shared by host workers. Not a multi-host limiter."""
    policies = {'send': ((10,10),(60,60)), 'create': ((20,3600),), 'search': ((30,60),),
                'group_create': ((5,86400),), 'group_invite': ((50,3600),),
                'group_manage': ((30,3600),)}

    def __init__(self, guard_file):
        self.guard_file = guard_file

    def __call__(self, category, user):
        rules = self.policies[category]
        now = time.time()
        key = hashlib.sha256(f'{category}:{user}'.encode()).hexdigest()
        try:
            with self.guard_file('nova-chat-rates') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                raw = handle.read()
                buckets = json.loads(raw) if raw else {}
                # No identities or content are persisted in rate files.
                retention = max(window for policy in self.policies.values() for _,window in policy)
                buckets = {k:[t for t in v if t > now-retention] for k,v in buckets.items()}
                buckets = {k:v for k,v in buckets.items() if v}
                history = buckets.get(key,[])
                if (key not in buckets and len(buckets)>=10000) or any(sum(t>now-window for t in history)>=limit for limit,window in rules):
                    raise ChatError('rate_limited','Please wait before trying again.',429)
                buckets[key] = [t for t in history if t>now-max(w for _,w in rules)] + [now]
                handle.seek(0)
                handle.truncate()
                json.dump(buckets,handle)
        except (OSError, ValueError, TypeError):
            # ChatError is ValueError; preserve safe intentional rate responses.
            raise


def register_nova_chat(app, get_db, guard_file, postgres=False):
    api = Blueprint('nova_chat',__name__,url_prefix='/api/nova-chat')
    service = DirectChat(get_db,postgres,ChatRateLimiter(guard_file))

    @api.before_request
    def authorize_request():
        if not current_user.is_authenticated:
            return jsonify(error='unauthorized',message='Sign in to continue.'),401
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            expected, supplied = session.get('csrf_token'), request.headers.get('X-CSRF-Token')
            if not isinstance(expected,str) or not supplied or not hmac.compare_digest(expected.encode(),supplied.encode()):
                return jsonify(error='csrf_failed',message='Refresh your session and try again.'),403
        request.max_content_length = 65536

    @api.after_request
    def private(response):
        response.headers['Cache-Control']='no-store'
        return response

    def run(operation):
        try:
            return jsonify(ok=True,**operation(int(current_user.id)))
        except ChatError as error:
            response = jsonify(error=error.code,message=error.message)
            response.status_code=error.status
            if error.status==429: response.headers['Retry-After']='3600' if request.endpoint=='nova_chat.direct' else '60'
            return response
        except RequestEntityTooLarge:
            return jsonify(error='request_too_large',message='Request body is too large.'),413
        except Exception:
            current_app.logger.error('Nova direct messaging operation failed')
            return jsonify(error='unavailable',message='Messaging is temporarily unavailable.'),503

    def body(fields=None):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or (fields is not None and set(data)!=set(fields)):
            raise ChatError('invalid_request','Invalid JSON request fields.')
        return data

    @api.post('/conversations/direct')
    def direct():
        return run(lambda uid:{'conversation':service.direct(uid,body({'recipient_id'})['recipient_id'])})

    @api.get('/conversations')
    def conversations():
        return run(lambda uid:service.conversations(uid,request.args.get('cursor'),request.args.get('limit',50)))

    @api.get('/conversations/<cid>')
    def conversation(cid):
        return run(lambda uid:{'conversation':service.conversation(uid,cid)})

    @api.get('/conversations/<cid>/messages')
    def messages(cid):
        return run(lambda uid:service.messages(uid,cid,request.args.get('cursor'),request.args.get('limit',50)))

    @api.post('/conversations/<cid>/messages')
    def send(cid):
        return run(lambda uid:{'message':service.send(uid,cid,body())})

    @api.put('/conversations/<cid>/receipts')
    def receipts(cid):
        return run(lambda uid:service.receipts(uid,cid,body()))

    @api.get('/blocks')
    def blocks():
        return run(lambda uid:service.blocks(uid,request.args.get('cursor'),request.args.get('limit',50)))

    @api.put('/blocks/<profile_id>')
    def block(profile_id):
        return run(lambda uid:service.block(uid,profile_id))

    @api.delete('/blocks/<profile_id>')
    def unblock(profile_id):
        return run(lambda uid:service.block(uid,profile_id,remove=True))

    @api.get('/users')
    def users():
        return run(lambda uid:service.search(uid,request.args.get('username')))

    app.register_blueprint(api)
    from services.nova_group_routes import register_nova_groups
    register_nova_groups(app, get_db, service.rate_limit, postgres)

"""Authenticated group adapters; direct-message routes remain separate."""
import hmac
from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user
from werkzeug.exceptions import RequestEntityTooLarge
from services.nova_chat import ChatError
from services.nova_groups import GroupChat


def register_nova_groups(app, get_db, rate_limit, postgres=False):
    api=Blueprint('nova_groups',__name__,url_prefix='/api/nova-chat/groups')
    service=GroupChat(get_db,postgres,rate_limit)

    @api.before_request
    def secure():
        if not current_user.is_authenticated:
            return jsonify(error='unauthorized',message='Sign in to continue.'),401
        if request.method in {'POST','PATCH','PUT','DELETE'}:
            expected,supplied=session.get('csrf_token'),request.headers.get('X-CSRF-Token')
            if not isinstance(expected,str) or not supplied or not hmac.compare_digest(expected.encode(),supplied.encode()):
                return jsonify(error='csrf_failed',message='Refresh your session and try again.'),403
        request.max_content_length=65536

    @api.after_request
    def private(response):
        response.headers['Cache-Control']='no-store'
        return response

    def run(operation):
        try:
            return jsonify(ok=True,**operation(int(current_user.id)))
        except ChatError as error:
            response=jsonify(error=error.code,message=error.message)
            response.status_code=error.status
            if error.status==429:
                response.headers['Retry-After']=('86400' if request.endpoint=='nova_groups.create'
                                                 else '60' if request.endpoint=='nova_groups.send' else '3600')
            return response
        except RequestEntityTooLarge:
            return jsonify(error='request_too_large',message='Request body is too large.'),413
        except Exception:
            current_app.logger.error('Nova group operation failed')
            return jsonify(error='unavailable',message='Groups are temporarily unavailable.'),503

    def body(fields=None):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or (fields is not None and set(data)!=set(fields)):
            raise ChatError('invalid_request','Invalid JSON request fields.')
        return data

    @api.post('')
    def create():
        def operation(user):
            data=body({'name','member_ids'})
            return {'group':service.create(user,data['name'],data['member_ids'])}
        return run(operation)

    @api.get('')
    def groups():
        return run(lambda user:service.groups(user,request.args.get('cursor'),request.args.get('limit',50)))

    @api.get('/invitations')
    def invitations():
        return run(lambda user:service.groups(user,request.args.get('cursor'),request.args.get('limit',50),invitations=True))

    @api.get('/<cid>')
    def group(cid):
        return run(lambda user:{'group':service.conversation(user,cid)})

    @api.patch('/<cid>')
    def rename(cid):
        return run(lambda user:service.rename(user,cid,body({'name'})['name']))

    @api.post('/<cid>/members')
    def invite(cid):
        return run(lambda user:service.invite(user,cid,body({'profile_id'})['profile_id']))

    @api.post('/<cid>/join')
    def join(cid):
        return run(lambda user:{'group':service.join(user,cid)})

    @api.post('/<cid>/leave')
    def leave(cid):
        return run(lambda user:service.leave(user,cid))

    @api.delete('/<cid>/members/<profile_id>')
    def remove(cid,profile_id):
        return run(lambda user:service.remove(user,cid,profile_id))

    @api.patch('/<cid>/members/<profile_id>')
    def role(cid,profile_id):
        return run(lambda user:service.role(user,cid,profile_id,body({'role'})['role']))

    @api.post('/<cid>/ownership')
    def transfer(cid):
        return run(lambda user:service.transfer(user,cid,body({'profile_id'})['profile_id']))

    @api.get('/<cid>/messages')
    def messages(cid):
        return run(lambda user:service.messages(user,cid,request.args.get('cursor'),request.args.get('limit',50)))

    @api.post('/<cid>/messages')
    def send(cid):
        return run(lambda user:{'message':service.send(user,cid,body())})

    @api.put('/<cid>/receipts')
    def receipts(cid):
        return run(lambda user:service.receipts(user,cid,body()))

    @api.get('/<cid>/events')
    def events(cid):
        return run(lambda user:service.events(user,cid,request.args.get('cursor'),request.args.get('limit',50)))

    app.register_blueprint(api)

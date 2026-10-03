"""Session-authenticated, CSRF-protected virtual trading JSON API."""
import hmac
from flask import Blueprint, jsonify, request, session
from flask_login import current_user
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from services.paper_trading import PaperTrading, PaperError


def register_paper_trading(app, factory, postgres=False, **options):
    api=Blueprint('paper',__name__,url_prefix='/api/markets/paper')
    service=PaperTrading(factory,postgres,**options)

    @api.before_request
    def protect():
        if not current_user.is_authenticated:
            return jsonify(error='unauthenticated',message='Sign in to Nova again.'),401
        if request.method=='POST':
            expected=session.get('csrf_token'); supplied=request.headers.get('X-CSRF-Token')
            if not expected or not supplied or not hmac.compare_digest(expected.encode(),supplied.encode()):
                return jsonify(error='csrf_failed',message='Reload Nova and try again.'),403

    @api.errorhandler(PaperError)
    def rejected(error):
        return jsonify(error=error.code,message=error.message),error.status

    @api.after_request
    def private(response):
        response.headers['Cache-Control']='no-store'
        return response

    def body(keys):
        request.max_content_length=2048
        try:data=request.get_json(silent=True)
        except (BadRequest,RequestEntityTooLarge):data=None
        if not isinstance(data,dict) or set(data)!=set(keys) or not all(isinstance(v,str) for v in data.values()):
            raise PaperError('invalid_request','Provide the expected JSON string fields.')
        return data

    def run(call):
        try:return jsonify(call())
        except PaperError:raise
        except Exception:
            # Never expose SQL, provider URLs, or upstream exception text.
            return jsonify(error='temporarily_unavailable',message='Simulated trading is temporarily unavailable. Please retry.'),503

    @api.get('/portfolio')
    def portfolio():return run(lambda:service.portfolio(int(current_user.id)))

    @api.get('/transactions')
    def transactions():return run(lambda:service.transactions(int(current_user.id),request.args.get('before')))

    @api.post('/preview')
    def preview():
        data=body(('symbol','side','unit','amount'))
        return run(lambda:service.preview(int(current_user.id),data))

    @api.post('/trades')
    def trades():
        data=body(('preview_id',))
        return run(lambda:service.execute(int(current_user.id),data['preview_id']))

    @api.post('/reset')
    def reset():
        data=body(('confirmation',))
        if data['confirmation']!='RESET PAPER PORTFOLIO':
            raise PaperError('confirmation_required','Type RESET PAPER PORTFOLIO to confirm.')
        return run(lambda:service.reset(int(current_user.id)))

    app.register_blueprint(api)

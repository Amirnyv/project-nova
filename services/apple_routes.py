"""Small Flask adapter; all billing authority lives in AppleBilling."""
import logging
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from services.apple_billing import AppleBilling
from services.apple_gateway import AppleBillingError

logger = logging.getLogger(__name__)


def register_apple_billing(app, get_db, postgres=False):
    api = Blueprint('apple_billing', __name__, url_prefix='/api/billing/apple')

    def body(fields):
        request.max_content_length = 70000
        try:
            data = request.get_json(silent=True)
        except (BadRequest, RequestEntityTooLarge):
            raise AppleBillingError('invalid_request') from None
        if not isinstance(data, dict) or set(data) != set(fields):
            raise AppleBillingError('invalid_request')
        return data

    def run(operation):
        try:
            return jsonify(operation(AppleBilling(get_db, postgres)))
        except AppleBillingError as error:
            logger.warning('apple_billing rejected code=%s', error.code)
            return jsonify(ok=False, error={'code': error.code, 'message': error.message}), error.http_status
        except Exception:
            # No exception repr/traceback: DB/provider exceptions may contain secrets.
            logger.error('apple_billing failed code=internal_error')
            return jsonify(ok=False, error={'code':'storage_unavailable',
                            'message':'Billing synchronization is temporarily unavailable. Please retry.'}), 503

    @api.post('/account-token')
    @login_required
    def account_token():
        def issue(service):
            body(())
            return service.issue_account_token(int(current_user.id))
        return run(issue)

    @api.post('/sync')
    @login_required
    def sync():
        return run(lambda service: service.sync(int(current_user.id), body(('signed_transaction',))['signed_transaction']))

    @api.post('/notifications')
    def notifications():
        return run(lambda service: service.notification(body(('signedPayload',))['signedPayload']))

    @api.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'no-store'
        return response

    app.register_blueprint(api)

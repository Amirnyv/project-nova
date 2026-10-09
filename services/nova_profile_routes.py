"""Cookie-authenticated Nova profile API; never invokes AI or billing."""
import fcntl
import hashlib
import hmac
import json
import time
from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user
from werkzeug.exceptions import RequestEntityTooLarge
from services.nova_profiles import ProfileError, get_profile, handle_available, update_profile


def register_nova_profiles(app, get_db, guard_file, postgres=False):
    api = Blueprint('nova_profiles', __name__, url_prefix='/api/nova-chat')

    @api.before_request
    def secure_request():
        if not current_user.is_authenticated:
            return jsonify(error='unauthorized', message='Sign in to continue.'), 401
        if request.method == 'PATCH':
            expected, supplied = session.get('csrf_token'), request.headers.get('X-CSRF-Token')
            if not isinstance(expected, str) or not supplied or not hmac.compare_digest(expected.encode(), supplied.encode()):
                return jsonify(error='csrf_failed', message='Refresh your session and try again.'), 403
        if request.endpoint == 'nova_profiles.availability':
            now = time.time()
            identities = [('user:' + str(current_user.id), 30), ('ip:' + (request.remote_addr or 'unknown'), 120)]
            try:
                with guard_file('nova-profile-rates') as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX)
                    raw = handle.read()
                    buckets = json.loads(raw) if raw else {}
                    buckets = {k: v for k, v in buckets.items() if v[1] > now}
                    keys = [(hashlib.sha256(k.encode()).hexdigest(), limit) for k, limit in identities]
                    if len(buckets) >= 10000 or any(buckets.get(k, [0])[0] >= limit for k, limit in keys):
                        return jsonify(error='rate_limited', message='Please wait before checking more handles.'), 429, {'Retry-After': '60'}
                    for key, _ in keys:
                        count, expiry = buckets.get(key, [0, now + 60])
                        buckets[key] = [count + 1, expiry]
                    handle.seek(0)
                    handle.truncate()
                    json.dump(buckets, handle)
            except (OSError, ValueError, TypeError):
                return jsonify(error='unavailable', message='Profile lookup is temporarily unavailable.'), 503

    @api.after_request
    def private(response):
        response.headers['Cache-Control'] = 'no-store'
        return response

    def run(operation):
        try:
            return jsonify(ok=True, **operation())
        except ProfileError as error:
            return jsonify(error=error.code, message=error.message), error.status
        except RequestEntityTooLarge:
            return jsonify(error='request_too_large', message='Profile request is too large.'), 413
        except Exception:
            current_app.logger.error('Nova profile operation failed')
            return jsonify(error='unavailable', message='Profiles are temporarily unavailable.'), 503

    @api.get('/profile')
    def profile():
        return run(lambda: {'profile': get_profile(get_db, int(current_user.id))})

    @api.patch('/profile')
    def patch_profile():
        request.max_content_length = 4096
        return run(lambda: {'profile': update_profile(get_db, int(current_user.id), request.get_json(silent=True), postgres)})

    @api.get('/username-availability')
    def availability():
        return run(lambda: handle_available(get_db, request.args.get('handle')))

    app.register_blueprint(api)

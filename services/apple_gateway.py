"""Apple official-library boundary. No credential reads or network calls on import."""
from dataclasses import dataclass
import os
from pathlib import Path


class AppleBillingError(Exception):
    MESSAGES = {
        'not_configured': ('Apple billing is not configured.', 503),
        'verification_failed': ('Apple purchase verification failed.', 400),
        'apple_unavailable': ('Apple verification is temporarily unavailable. Please retry.', 503),
        'invalid_request': ('Provide only the required Apple billing fields.', 400),
        'unsupported_product': ('This Apple product is not supported by Nova.', 400),
        'ownership_conflict': ('This Apple subscription cannot be linked to this Nova account.', 409),
        'account_token_required': ('Purchase with your Nova account token, or contact support to restore this purchase.', 409),
        'storage_unavailable': ('Billing synchronization is temporarily unavailable. Please retry.', 503),
    }

    def __init__(self, code):
        self.code = code
        self.message, self.http_status = self.MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class AppleConfig:
    environment: str
    bundle_id: str
    app_id: int
    key_id: str
    issuer_id: str
    private_key_path: str
    root_paths: tuple

    @classmethod
    def load(cls):
        try:
            environment = os.environ.get('APPLE_ENVIRONMENT', 'Production')
            if environment not in {'Production', 'Sandbox'}:
                raise ValueError()
            values = [os.environ.get(k, '').strip() for k in
                      ('APPLE_KEY_ID', 'APPLE_ISSUER_ID', 'APPLE_PRIVATE_KEY_PATH', 'APPLE_ROOT_CA_PATHS')]
            if not all(values):
                raise ValueError()
            bundle = os.environ.get('APPLE_BUNDLE_ID', 'com.amirnyv.Nova').strip()
            app_id = int(os.environ.get('APPLE_APP_ID', '6817116419'))
            # These are this application's public identifiers, never client-selected.
            if bundle != 'com.amirnyv.Nova' or app_id != 6817116419:
                raise ValueError()
            roots = tuple(p.strip() for p in values[3].split(',') if p.strip())
            if not roots:
                raise ValueError()
            return cls(environment, bundle, app_id, *values[:3], roots)
        except (ValueError, TypeError):
            raise AppleBillingError('not_configured') from None


class AppleGateway:
    def __init__(self, config):
        self.config = config
        try:
            from appstoreserverlibrary.api_client import AppStoreServerAPIClient
            from appstoreserverlibrary.models.Environment import Environment
            from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
            environment = Environment(config.environment)
            roots = [Path(path).read_bytes() for path in config.root_paths]
            key = Path(config.private_key_path).read_bytes()
            self.verifier = SignedDataVerifier(roots, True, environment, config.bundle_id, config.app_id)
            self.client = AppStoreServerAPIClient(key, config.key_id, config.issuer_id, config.bundle_id, environment)
        except Exception:
            raise AppleBillingError('not_configured') from None

    def _verify(self, method, payload):
        if not isinstance(payload, str) or not 1 <= len(payload) <= 65536:
            raise AppleBillingError('invalid_request')
        try:
            return getattr(self.verifier, method)(payload)
        except Exception as error:
            # The official verifier distinguishes transient OCSP/network failures.
            status = getattr(getattr(error, 'status', None), 'name', '')
            code = 'apple_unavailable' if status == 'RETRYABLE_VERIFICATION_FAILURE' else 'verification_failed'
            raise AppleBillingError(code) from None

    def transaction(self, payload):
        return self._verify('verify_and_decode_signed_transaction', payload)

    def renewal(self, payload):
        return self._verify('verify_and_decode_renewal_info', payload)

    def notification(self, payload):
        return self._verify('verify_and_decode_notification', payload)

    def statuses(self, transaction_id):
        try:
            return self.client.get_all_subscription_statuses(transaction_id)
        except Exception:
            # No provider exception string, authorization headers, or response body escapes.
            raise AppleBillingError('apple_unavailable') from None

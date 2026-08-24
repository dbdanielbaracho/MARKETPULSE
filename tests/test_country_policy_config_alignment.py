from pathlib import Path

import yaml

from app.services.country_policy import configured_country_policies, resolve_country_policy


REQUIRED_POLICY_FIELDS = {
    'audience',
    'informational_content_allowed',
    'commercial_outbound_allowed',
    'paid_social_allowed',
    'minimum_age',
    'route_mode',
    'reason',
}


def test_every_configured_country_pack_is_the_runtime_policy_source_of_truth():
    packs = []
    configured_country_policies.cache_clear()
    for path in sorted(Path('config/countries').glob('*.yaml')):
        payload = yaml.safe_load(path.read_text(encoding='utf-8'))
        packs.append(payload)
        assert set(payload['policy']) == REQUIRED_POLICY_FIELDS
        policy = resolve_country_policy(payload['country_code'])
        assert policy.country == payload['country_code']
        assert policy.audience == payload['policy']['audience']
        assert policy.informational_content_allowed == payload['policy']['informational_content_allowed']
        assert policy.commercial_outbound_allowed == payload['policy']['commercial_outbound_allowed']
        assert policy.paid_social_allowed == payload['policy']['paid_social_allowed']
        assert policy.minimum_age == payload['policy']['minimum_age']
        assert policy.route_mode == payload['policy']['route_mode']
        assert policy.reason == payload['policy']['reason']

    assert {item['country_code'] for item in packs} == {'US', 'GB', 'BR'}


def test_disabled_country_packs_remain_commercially_fail_closed():
    configured_country_policies.cache_clear()
    for path in sorted(Path('config/countries').glob('*.yaml')):
        payload = yaml.safe_load(path.read_text(encoding='utf-8'))
        if payload['enabled']:
            continue
        policy = resolve_country_policy(payload['country_code'])
        assert payload['features']['outbound'] is False
        assert policy.commercial_outbound_allowed is False
        assert policy.paid_social_allowed is False
        assert policy.route_mode == 'informational_only'


def test_country_policy_module_does_not_duplicate_known_country_business_rules():
    source = Path('app/services/country_policy.py').read_text(encoding='utf-8')
    assert '_POLICIES' not in source
    for business_value in ('us_global', 'uk_informational', 'brazil_informational'):
        assert business_value not in source
